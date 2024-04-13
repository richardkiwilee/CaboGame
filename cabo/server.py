import time
from concurrent import futures
import queue
import random
import json
import grpc
import cabo.protocol.service_pb2 as pb2
import cabo.protocol.service_pb2_grpc as rpc
from cabo.core import GameManager, GameStatus, create_seed
from concurrent.futures import ThreadPoolExecutor


caboroomUsers = {}
caboroomNames = set()
queues = []


class CaboRoomServicer(rpc.CaboRoomServicer):
    def __init__(self):
        self.gm = GameManager()
        self.gm.game_status = GameStatus.LOBBY.value
        self.host = None
        self.seq = 0

    def Register(self, request, context):
        cname = request.name
        if len(caboroomUsers) == 0:
            self.host = cname
        if cname is None or len(cname) >= 32:
            return pb2.GeneralResponse(ok=False, msg='Illegal name')
        if cname in caboroomNames:
            return pb2.GeneralResponse(ok=False, msg='This name has been used')

        caboroomNames.add(cname)
        caboroomUsers[cname] = {
            'name': cname
        }
        self._putToQueues({
            'type': pb2.Broadcast.USER_JOIN,
            'name': cname
        })

        print('User [{}] registered.'.format(cname))
        self.gm.player_join(cname)
        self.gm.ready_status[cname] = False
        print('return ready_status:', self.gm.ready_status)
        return pb2.GeneralResponse(ok=True, name=cname, msg=json.dumps(self.gm.ready_status))

    def Handle(self, request, context):
        print('User [{}] sent message: {}'.format(request.name, request.msg))
        if not self._isAuthorized(request):
            return pb2.GeneralResponse(ok=False, msg='Not authorized')
        if len(request.msg.strip()) == 0:
            return pb2.GeneralResponse(ok=False, msg='Empty message')
        if self.gm.game_status == GameStatus.LOBBY.value or self.gm.game_status == GameStatus.ROUND_GAP.value:
            if request.msg == 'start' and self.host != request.name:
                return pb2.GeneralResponse(ok=False, msg='You are not the host')
            if self.host == request.name and request.msg == 'start':
                if len(caboroomUsers) == 1:
                    return pb2.GeneralResponse(ok=False, msg='You are the only one here')
                if not all(self.gm.ready_status.values()):
                    return pb2.GeneralResponse(ok=False, msg='Not all players are ready')
                if self.gm.game_status == GameStatus.LOBBY.value:
                    self._putToQueues({
                        'type': pb2.Broadcast.GAME_START,
                        'name': 'server',
                        'seq': 0
                    })
                print('Game started')
                self.gm.game_status = GameStatus.PLAYING.value
                _seed = create_seed(len(caboroomUsers))
                print('Seed:', _seed)
                _order = self.gm.turnorder.shuffle()
                print('Order:', _order)
                peek_dict = dict()
                for user in caboroomUsers:
                    peek_dict[user] = []
                    while len(set(peek_dict[user])) < 2:
                        _index = random.randint(0, 3)
                        peek_dict[user].append(_index)
                self.gm.new_round(_seed.decode(), _order, peek_dict)
                self._putToQueues({
                    'type': pb2.Broadcast.NEW_ROUND,
                    'seq': 0,
                    'name': 'server',
                    'msg': json.dumps({'seed': _seed.decode(), 'order': _order, 'peek': peek_dict})
                })
                self._putToQueues({
                    'type': pb2.Broadcast.PLAYER_TURN,
                    'seq': 0,
                    'name': 'server',
                    'msg': self.gm.turnorder.current()
                })
                return pb2.GeneralResponse(ok=True, msg='Game started')
            elif request.msg == 'ready' and self.gm.game_status in (GameStatus.LOBBY.value, GameStatus.ROUND_GAP.value):
                self.gm.ready_status[request.name] = True
                self._putToQueues({
                    'type': pb2.Broadcast.USER_READY,
                    'seq': 0,
                    'name': request.name,
                    'msg': json.dumps(self.gm.ready_status)
                })
                return pb2.GeneralResponse(ok=True, name=request.name, msg='Ready')
        elif self.gm.game_status == GameStatus.PLAYING.value:
            if self.gm.turnorder.current() != request.name:
                return pb2.GeneralResponse(ok=False, msg='Not your turn')
            print('receive request:', request)
            if self.gm.valid_action(request):
                self.gm.handle(request)
                curUser = caboroomUsers[request.name]
                self._putToQueues({
                    'type': pb2.Broadcast.PLAYER_ACTION,
                    'seq': self.gm.seq,
                    'name': curUser['name'],
                    'msg': request.msg
                })
                self.seq += 1
                if not self.gm.is_round_end():
                    self._putToQueues({
                        'type': pb2.Broadcast.PLAYER_TURN,
                        'seq': 0,
                        'name': 'server',
                        'msg': self.gm.turnorder.current()
                    })
                    print('next turn:', self.gm.turnorder.current())
                else:
                    self.gm.round_end()
                    if not self.gm.check_game_finish():
                        self._putToQueues({
                            'type': pb2.Broadcast.ROUND_END,
                            'seq': 0,
                            'name': 'server',
                            'msg': ''
                        })
                        print('round end')
                    else:
                        self.gm.game_end()
                        self._putToQueues({
                            'type': pb2.Broadcast.GAME_END,
                            'seq': 0,
                            'name': 'server',
                            'msg': ''
                        })
                        print('game end')
                        self.gm.clear_score()
                return pb2.GeneralResponse(ok=True, msg='OK')
            else:
                return pb2.GeneralResponse(ok=False, msg='Invalid action')

    def Subscribe(self, request, context):
        if not self._isAuthorized(request):
            return pb2.Broadcast()

        if 'stream' in caboroomUsers[request.name]:
            return pb2.Broadcast(type=pb2.Broadcast.FAILURE, msg='Already subscribed')

        cb_added = context.add_callback(self._onDisconnectWrapper(request, context))

        if not cb_added:
            print('Warning: disconnection will not be called')

        q = queue.Queue()
        queues.append(q)
        caboroomUsers[request.name]['stream'] = q
        yield pb2.Broadcast(type=pb2.Broadcast.UNSPECIFIED)

        while True:
            q = caboroomUsers[request.name]['stream']
            obj = q.get()
            if obj is None:
                yield pb2.Broadcast(type=pb2.Broadcast.FAILURE, msg='The server is shutting down')
                return
            yield pb2.Broadcast(**obj)
            q.task_done()

    def _putToQueues(self, obj):
        for _, user in caboroomUsers.items():
            if 'stream' in user:
                user['stream'].put(obj)

    def _isAuthorized(self, request):
        return not(request.name is None or request.name not in caboroomUsers)

    def _onDisconnectWrapper(self, request, context):
        # Be careful! The error here is silently ignored!
        def callback():
            curUser = request.name
            print('User [{}] disconnected.'.format(curUser['name']))
            self._putToQueues({
                'type': pb2.Broadcast.USER_LEAVE,
                'name': curUser['name']
            })
            del curUser['stream']
            self.gm.player_exit(curUser['name'])
        return callback


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=8))
    rpc.add_CaboRoomServicer_to_server(CaboRoomServicer(), server)
    server.add_insecure_port('[::]:50051')
    server.start()
    print('>>> Server started')
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print('>>> Exiting')
        # to unblock all queues
        for q in queues:
            q.put(None)
        server.stop(0)


if __name__ == '__main__':
    serve()
