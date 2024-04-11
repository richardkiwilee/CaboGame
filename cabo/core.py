import random
import base64
import os
import json
from enum import Enum
from rich.table import Table
from rich.console import Console
import cabo.protocol.service_pb2 as pb2
NUMBER_PEAK = 8
NUMBER_SPY = 9
NUMBER_SWITCH = 10

_DEBUG = True
class MainAction(Enum):
    SYSTEM = 0
    DRAW = 1
    DRAW_DISCARD = 2
    CABO = 3
    READY = 4
    SYNC = 5


class SubAction(Enum):
    DISCARD = 1
    CHANGE = 2      # 与自己交换
    PEAK = 3
    SPY = 4
    SWITCH = 5      # 发动卡片效果与别人交换


class SCORE(Enum):
    LOSE = 0
    WIN = 1
    SOMEONE_KAMIKAZE = 2


class Color(Enum):
    RED = 'red'
    GREEN = 'green'
    BLUE = 'blue'
    YELLOW = 'yellow'
    MAGENTA = 'magenta'
    CYAN = 'cyan'


COLOR_ORDER = [Color.RED, Color.GREEN, Color.BLUE, Color.YELLOW, Color.MAGENTA, Color.CYAN]


def create_seed(players=4):
    deck = [0, 0, 13, 13,
            1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4,
            5, 5, 5, 5, 6, 6, 6, 6, 7, 7, 7, 7, 8, 8, 8, 8,
            9, 9, 9, 9, 10, 10, 10, 10, 11, 11, 11, 11, 12, 12, 12, 12]
    if 4 < players <= 8:
        deck = deck * 2
    random.shuffle(deck)
    _ = ''.join(['%02d' % i for i in deck])
    return base64.b64encode(_.encode('utf-8'))


class PlayerTurnOrder:
    def __init__(self):
        self.turnorder = []
        self.index = 0

    def setCurrent(self, player):
        self.index = self.turnorder.index(player)
    def AddPlayer(self, player):
        self.turnorder.append(player)

    def RemovePlayer(self, player):
        self.turnorder.remove(player)

    def shuffle(self):
        random.shuffle(self.turnorder)
        self.index = 0
        return [player for player in self.turnorder]

    def next(self) -> str:
        if self.index + 1 >= len(self.turnorder):
            self.index = 0
        else:
            self.index += 1
        print('next index:', self.index)
        return self.turnorder[self.index]

    def current(self) -> str:
        return self.turnorder[self.index]


class Card:
    def __init__(self, number: int):
        self.number = number
        # 0暗牌 1已偷看 2明牌
        self.face_up = False
        self.peak = set()

    def peaked_by(self, player):
        if player not in self.peak:
            self.peak.add(player)

    def to_json(self):
        return json.dumps(self.__dict__)

    @classmethod
    def from_json(cls, json_str):
        data = json.load(json_str)
        return cls(**data)

    def print(self):
        print(f'{self.number}', end='')
        if self.number == NUMBER_PEAK:
            print('[ PEAK ]', end='')
        if self.number == NUMBER_SPY:
            print('[  SPY ]', end='')
        if self.number == NUMBER_SWITCH:
            print('[SWITCH]', end='')


class Player:
    def __init__(self, username: str, color: Color):
        self.username = username
        self.color = color
        self.hand = []
        self.score = 0
        self.reborn = False  # 是否执行过reborn
        self.cabo = False  # 是否宣告cabo

    def rich_username(self):
        return f'[bold on {self.color}]{self.username}[/bold on {self.color}]'

    def reset(self):
        self.hand = []
        self.reborn = False
        self.cabo = False

    def AddCard(self, card):
        self.hand.append(card)

    def GetCard(self, index) -> Card:
        return self.hand[index]

    def SetCard(self, index, card: Card):
        self.hand[index] = card

    def RemoveCard(self, index) -> Card:
        return self.hand.pop(index)

    def GetHandsCount(self) -> int:
        return len(self.hand)

    def GetHandScore(self) -> int:
        return sum([card.number for card in self.hand] + [0])

    def IsKamikaze(self) -> bool:
        hand = [card.number for card in self.hand]
        hand.sort()
        return hand == [12, 12, 13, 13]

    def UpdateScore(self, status):
        if status == SCORE.LOSE:
            self.score += sum([card.number for card in self.hand] + [0])
            if self.cabo:
                self.score += 10
        if status == SCORE.SOMEONE_KAMIKAZE:
            self.score += 50
        if status == SCORE.WIN:
            pass
        if self.score == 100:
            self.score = 50
            self.reborn = True


class GameStatus(Enum):
    LOBBY = 1
    PLAYING = 2
    ROUND_GAP = 3


class GameManager:
    def __init__(self):
        self.players = dict()       # key: str username, value: Player
        self.ready_status = dict()  # key: str username, value: bool
        self.game_status = GameStatus.LOBBY.value
        self.turnorder = PlayerTurnOrder()
        self.draw = []      # 抽牌堆
        self.seq = 0        # 当前sequence
        self.discard = []   # 抽牌堆

    def player_join(self, username):
        if username not in self.players.keys():
            self.players[username] = Player(username, COLOR_ORDER.pop())
            self.turnorder.AddPlayer(username)

    def player_exit(self, username):
        if username in self.players.keys():
            COLOR_ORDER.append(self.players[username].color)
            self.players.pop(username)
            self.turnorder.RemovePlayer(username)

    def clear_score(self):
        for player in self.players.values():
            player.score = 0
    def new_round(self, _seed, order: list):
        self.game_status = GameStatus.PLAYING.value
        self.turnorder.turnorder = order
        deck = base64.b64decode(_seed)
        self.draw = [int(deck[i:i + 2]) for i in range(0, len(deck), 2)]
        self.discard = []
        print('new round players:', self.players)
        for username in self.turnorder.turnorder:
            player = self.players[username]     # type: Player
            player.reset()
            for i in range(0, 4):
                player.AddCard(Card(self.draw.pop(0)))
        _first_discard = Card(self.draw.pop(0))
        _first_discard.face_up = True
        self.discard.append(_first_discard)

    def handle(self, message):
        # 只处理handle_action
        print(f'receive {message}')
        user = message.name
        body = message.msg
        player = self.players[user]
        if ' ' in body:
            action = body.split(' ')[0]
            param = body.split(' ')[1]
        else:
            action = body
            param = ''
        if action == 'draw&peak':
            top_card = Card(self.draw.pop(0))  # type: Card
            top_card.face_up = True
            self.discard.append(top_card)
            index = int(param)
            card = player.GetCard(index)
            card.peaked_by(user)
        if action == 'draw&spy':
            top_card = Card(self.draw.pop(0))  # type: Card
            top_card.face_up = True
            self.discard.append(top_card)
            target_name = param.split(':')[0]
            target_index = int(param.split(':')[1])
            target_player = self.players[target_name]
            card = target_player.GetCard(target_index)
            card.peaked_by(user)
        if action == 'draw&switch':
            top_card = Card(self.draw.pop(0))  # type: Card
            top_card.face_up = True
            self.discard.append(top_card)
            my_index = int(param.split(',')[0])
            card1 = player.GetCard(my_index)
            target_name = param.split(',')[1].split(':')[0]
            target_index = int(param.split(',')[1].split(':')[1])
            target_player = self.players[target_name]
            card2 = target_player.GetCard(target_index)
            _ = card2
            target_player.SetCard(target_index, card1)
            player.SetCard(my_index, _)
        if action == 'draw&change':
            top_card = Card(self.draw.pop(0))  # type: Card
            top_card.peaked_by(user)
            if ',' not in param:
                index = int(param)
                card = player.GetCard(index)
                card.face_up = True
                print(f'{user}抽取了{top_card.number}, 与{card.number}交换')
                self.discard.append(card)
                player.SetCard(index, top_card)
            else:
                indexes = [int(i) for i in param.split(',')]
                indexes.sort(reverse=True)
                tmp = set()
                for index in indexes:
                    card = player.GetCard(index)
                    tmp.add(card.number)
                if len(tmp) == 1:
                    print(f'{user}抽取了{top_card.number}, 多重交换成功')
                    for index in indexes:
                        print(f'交换了{index}的{player.GetCard(index).number}')
                        _card = player.RemoveCard(index)
                        _card.face_up = True
                        self.discard.append(_card)
                    player.AddCard(top_card)
                else:
                    print(f'{user}抽取了{top_card.number}, 多重交换失败')
                    for index in indexes:
                        _card = player.GetCard(index)
                        _card.face_up = True
                    player.AddCard(top_card)
        if action == 'draw&discard':
            top_card = Card(self.draw.pop(0))  # type: Card
            top_card.face_up = True
            self.discard.append(top_card)
        if action == 'discard&draw':
            top_card = self.discard.pop()  # type: Card
            if ',' not in param:
                index = int(param)
                card = player.GetCard(index)
                card.face_up = True
                self.discard.append(card)
                player.SetCard(index, top_card)
            else:
                indexes = [int(i) for i in param.split(',')]
                indexes.sort(reverse=True)
                tmp = set()
                for index in indexes:
                    card = player.GetCard(index)
                    tmp.add(card.number)
                if len(tmp) == 1:
                    for index in indexes:
                        _card = player.RemoveCard(index)
                        _card.face_up = True
                        self.discard.append(_card)
                    player.AddCard(top_card)
                else:
                    for index in indexes:
                        _card = player.GetCard(index)
                        _card.face_up = True
                    player.AddCard(top_card)
        if action == 'cabo':
            player.cabo = True
        self.refresh()
        next_player = self.players[self.turnorder.next()]
        if next_player.cabo:
            self.game_status = GameStatus.ROUND_GAP.value

    def someoneCaboed(self):
        for player in self.players.values():
            if player.cabo:
                return True
        return False
    def rich_card(self, card: Card):
        number = card.number
        rich_str = '%2d' % number
        for username in self.turnorder.turnorder:
            if username in card.peak:
                rich_str += f'[bold on {self.players[username].color}] [/bold on {self.players[username].color}]'
            else:
                rich_str += ' '
        return rich_str

    def valid_action(self, request) -> bool:
        msg = request.msg
        return True


    def refresh_ready(self):
        if not _DEBUG:
            _ = os.system('cls')
        print('ready status', self.ready_status)
        table = Table()
        table.add_column('Id', justify='center')
        table.add_column('用户名', justify='center')
        table.add_column('准备状态', justify='center')
        for index in range(0, len(self.turnorder.turnorder)):
            _id = index + 1
            user = self.turnorder.turnorder[index]
            player = self.players[user]     # type: Player
            if self.turnorder.current() == user:
                rich_id = f'[bold on green]{_id}[/bold on green]'
            else:
                rich_id = f'{_id}'
            table.add_row(f'{rich_id}',
                          f'{player.rich_username()}',
                          f'{"已准备" if self.ready_status[user] else "未准备"}'
                          )
        console = Console()
        console.print(table)

    def refresh(self, msg=None):
        if not _DEBUG:
            _ = os.system('cls')
        if self.game_status == GameStatus.LOBBY.value:
            return self.refresh_ready()
        table = Table()
        table.add_column('Id', justify='center')
        table.add_column('分数', justify='center')
        table.add_column('用户名', justify='center')
        max_hand = max([len(player.hand) for player in self.players.values()])
        for i in range(max_hand):
            table.add_column(f'手牌{i}', justify='center')
        table.add_column(f'动态', justify='center', style='magenta')

        for index in range(0, len(self.turnorder.turnorder)):
            _id = index + 1
            user = self.turnorder.turnorder[index]
            player = self.players[user]     # type: Player
            if self.turnorder.current() == user:
                rich_id = f'[bold on green]{_id}[/bold on green]'
            else:
                rich_id = f'{_id}'
            if player.reborn:
                rich_score = f'[bold on red]{player.score}[/bold on red]'
            else:
                rich_score = f'{player.score}'
            table.add_row(f'{rich_id}',
                          f'{rich_score}',
                          f'{player.rich_username()}',
                          *[self.rich_card(card) if i < len(player.hand) else '' for i, card in enumerate(player.hand)],
                          f'{"CABO" if player.cabo else ""}'
                          )
        console = Console()
        console.print(table)

    def print_score(self):
        if not _DEBUG:
            _ = os.system('cls')
        table = Table()
        table.add_column('Id', justify='center')
        table.add_column('分数', justify='center')
        table.add_column('用户名', justify='center')
        max_hand = max([len(player.hand) for player in self.players.values()])
        for i in range(max_hand):
            table.add_column(f'手牌{i}', justify='center')
        table.add_column(f'动态', justify='center', style='magenta')

        for index in range(0, len(self.turnorder.turnorder)):
            _id = index + 1
            user = self.turnorder.turnorder[index]
            player = self.players[user]  # type: Player
            if player.reborn:
                rich_score = f'[bold on red]{player.score}[/bold on red]'
            else:
                rich_score = f'{player.score}'
            user = self.turnorder.turnorder[index]
            player = self.players[user]     # type: Player
            table.add_row(f'{_id}',
                          f'{rich_score}',
                          f'{player.rich_username()}',
                          *[self.rich_card(card) if i < len(player.hand) else '' for i, card in enumerate(player.hand)],
                          f'{"CABO" if player.cabo else ""}'
                          )
        console = Console()
        console.print(table)

    def is_round_end(self) -> bool:
        return self.game_status == GameStatus.ROUND_GAP.value

    def round_end(self):
        self.game_status = GameStatus.ROUND_GAP.value
        tmp = [player.username for player in self.players.values() if player.IsKamikaze()]
        if not tmp:
            tmp = {player.username: player.GetHandScore() for player in self.players.values()}
            winner = min(tmp, key=tmp.get)
            for player in self.players.values():
                if player.username == winner:
                    player.UpdateScore(SCORE.WIN)
                else:
                    player.UpdateScore(SCORE.LOSE)
        else:
            winner = tmp[0]
            for player in self.players.values():
                if player.username == winner:
                    player.UpdateScore(SCORE.WIN)
                else:
                    player.UpdateScore(SCORE.SOMEONE_KAMIKAZE)
        for name, player in self.players.items():
            self.ready_status[name] = False
        self.print_score()
        for player in self.ready_status.keys():
            self.ready_status[player] = False
        print('print READY to next round...')

    def game_end(self):
        self.game_status = GameStatus.LOBBY.value
        tmp = [player.username for player in self.players.values() if player.IsKamikaze()]
        if not tmp:
            tmp = {player.username: player.GetHandScore() for player in self.players.values()}
            winner = min(tmp, key=tmp.get)
            for player in self.players.values():
                if player.username == winner:
                    player.UpdateScore(SCORE.WIN)
                else:
                    player.UpdateScore(SCORE.LOSE)
        else:
            winner = tmp[0]
            for player in self.players.values():
                if player.username == winner:
                    player.UpdateScore(SCORE.WIN)
                else:
                    player.UpdateScore(SCORE.SOMEONE_KAMIKAZE)
        for name, player in self.players.items():
            self.ready_status[name] = False
        self.print_score()
        for player in self.ready_status.keys():
            self.ready_status[player] = False
        print('print READY to next game...')

    def check_game_finish(self):
        for name, player in self.players.items():
            if player.score > 100:
                return True
        return False
