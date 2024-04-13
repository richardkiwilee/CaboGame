import time

import grpc
import threading
import queue
import sys
import random
import string
import threading
import grpc
import argparse
import json
import os
import cabo.protocol.service_pb2 as pb2
import cabo.protocol.service_pb2_grpc as rpc
from cabo.core import GameManager, Card, NUMBER_peek, NUMBER_SPY, NUMBER_SWITCH, GameStatus


class Client:
    def __init__(self, username: str, address='localhost', port=50051):
        self.username = username
        # 创建 gRPC 通道和存根
        channel = grpc.insecure_channel(address + ':' + str(port))
        self.stub = rpc.CaboRoomStub(channel)
        # 启动一个新线程监听消息
        self.gm = GameManager()
        registerResp = self.stub.Register(pb2.GeneralRequest(name=self.username))
        if not registerResp.ok:
            print('Failed to register chatroom: {}'.format(registerResp.msg))
            return
        self.gm.player_join(self.username)
        self.gm.ready_status = json.loads(registerResp.msg)
        for player in self.gm.ready_status:
            if player not in self.gm.players.keys():
                self.gm.player_join(player)
        listening = threading.Thread(target=self.__listen_for_messages, daemon=True)
        listening.start()
        input_queue = queue.Queue()
        input_thread = threading.Thread(target=self.add_input, args=(input_queue, self.stub))
        input_thread.daemon = True
        input_thread.start()

    def add_input(self, input_queue, stub):
        while True:
            try:
                message = input("").lower()
                if message == 'exit':
                    break
                action = message.split(' ')[0]
                if self.gm.game_status in (GameStatus.LOBBY.value, GameStatus.ROUND_GAP.value):
                    if action == 'cls':
                        _ = os.system('cls')
                        self.gm.refresh(username=self.username)
                    if action == 'ready':
                        self.sendMessage(action)
                    if action == 'start':
                        self.sendMessage(action)
                if self.gm.game_status == GameStatus.PLAYING.value:
                    if action == 'cls':
                        _ = os.system('cls')
                        self.gm.refresh(username=self.username)
                    if action == 'draw':
                        # 从牌堆顶抽一张牌 选择操作
                        if self.gm.turnorder.current() != self.username:
                            print('Not your turn')
                            continue
                        card = Card(self.gm.draw[0])       # type: Card
                        print(f"抽到的牌是: ", end="")
                        card.print()
                        print("请选择操作[change/discard/use]: ", end="")
                        while True:
                            try:
                                message2 = input("").lower()
                                if message2 == 'change':
                                    param = input("请输入要交换的牌的编号: ")
                                    print('try to send: ', f'draw&change {param}')
                                    self.sendMessage(f'draw&change {param}')
                                    break
                                if message2 == 'discard':
                                    self.sendMessage('draw&discard')
                                    break
                                if message2 == 'use':
                                    if card.number == NUMBER_peek:
                                        param = input("请输入要查看的牌的编号: ")
                                        self.sendMessage(f'draw&peek {param}')
                                        break
                                    elif card.number == NUMBER_SPY:
                                        param = input("请输入要查看的玩家与牌的编号: ")
                                        self.sendMessage(f'draw&spy {param}')
                                        break
                                    elif card.number == NUMBER_SWITCH:
                                        _param1 = input("请输入要交换的牌的编号: ")
                                        _param2 = input("请输入要交换的玩家与牌的编号[name:id]: ")
                                        param = f'{_param1},{_param2}'
                                        self.sendMessage(f'draw&switch {param}')
                                        break
                            except KeyboardInterrupt:
                                pass
                    if action == 'dd':
                        # 用弃牌堆顶的排与手牌交换
                        if self.gm.turnorder.current() != self.username:
                            print('Not your turn')
                            continue
                        if len(self.gm.discard) == 0:
                            print('No card to draw')
                            continue
                        index = message.split(' ')[1]
                        self.sendMessage(f'discard&draw {index}')
                    if action == 'cabo':
                        if self.gm.turnorder.current() != self.username:
                            print('Not your turn')
                            continue
                        if self.gm.someoneCaboed():
                            print('You can\'t cabo now')
                            continue
                        self.sendMessage('cabo')
            except KeyboardInterrupt:
                pass
            except Exception as ex:
                self.gm.refresh(username=self.username)
                print(f'Input Error: {ex}')

    def __listen_for_messages(self):
        # 从服务器接收新消息并显示
        subscribeResps = self.stub.Subscribe(pb2.GeneralRequest(name=self.username))
        subscribeResp = next(subscribeResps)
        if subscribeResp is None:
            print('Failed to subscribe game.')
            return
        print('Successfully joined the game.')
        self.gm.refresh_ready()
        for resp in subscribeResps:
            if resp.type == pb2.Broadcast.UNSPECIFIED:
                print(f'Unspecified: {resp.msg}')
            elif resp.type == pb2.Broadcast.FAILURE:
                print(f'Failure: {resp.msg}')
            elif resp.type == pb2.Broadcast.USER_JOIN:
                print(f'{resp.name} has joined the game.')
                self.gm.player_join(resp.name)
                self.gm.ready_status[resp.name] = False
                self.gm.refresh_ready()
            elif resp.type == pb2.Broadcast.USER_LEAVE:
                print(f'{resp.name} has lefted the game.')
                self.gm.player_exit(resp.msg)
                self.gm.refresh_ready()
            elif resp.type == pb2.Broadcast.USER_READY:
                print(f'{resp.name} is ready.')
                body = json.loads(resp.msg)
                self.gm.ready_status = body
                self.gm.refresh_ready()
            elif resp.type == pb2.Broadcast.GAME_START:
                self.gm.clear_score()
                self.gm.game_status = GameStatus.PLAYING.value
            elif resp.type == pb2.Broadcast.NEW_ROUND:
                msg = json.loads(resp.msg)
                _seed = msg['seed']
                _order = msg['order']
                _peek = msg['peek']
                mask_peek = dict()
                mask_peek[self.username] = _peek[self.username]
                self.gm.new_round(_seed, _order, peek_dict=mask_peek)
                self.gm.refresh(username=self.username)
            elif resp.type == pb2.Broadcast.GAME_END:
                self.gm.game_end()
            elif resp.type == pb2.Broadcast.ROUND_END:
                self.gm.round_end()
            elif resp.type == pb2.Broadcast.PLAYER_TURN:
                print(f'{resp.msg}\'s turn.')
                self.gm.turnorder.setCurrent(resp.msg)
                self.gm.refresh(username=self.username)
            elif resp.type == pb2.Broadcast.PLAYER_ACTION:
                print(f'{resp.name} do: {resp.msg}')
                self.gm.handle(resp)
                self.gm.refresh(msg=resp, username=self.username)
            else:
                print(f'Unknown message: {resp}')

    def sendMessage(self, msg):
        resp = self.stub.Handle(pb2.GeneralRequest(name=self.username, msg=msg))
        print(resp.msg)


def main(address='localhost', port=50051, username=None):
    chars = string.ascii_letters
    if username is None:
        username = ''.join(random.choice(chars) for _ in range(5))
    client = Client(username, address, port)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print('Bye')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Bye')
