from cabo.server import serve
from cabo.client import main
import threading


if __name__ == '__main__':
    while True:
        _ = input("输入host/join:")
        if _.lower() == 'host':
            while True:
                _ = input("输入端口号[50051]:")
                if _ == '':
                    _ = '50051'
                    break
                else:
                    try:
                        _ = int(_)
                        break
                    except Exception as ex:
                        print(f'输入错误: {ex}')
            server_thread = threading.Thread(target=serve, args=(_,))
            server_thread.start()
            while True:
                try:
                    username = input("输入用户名:")
                    if username != '':
                        try:
                            main('localhost', _, username)
                        except Exception as ex:
                            pass
                except Exception as ex:
                    pass
        elif _.lower() == 'join':
            while True:
                _ = input("输入(冒号分割) host:port\n")
                if _ == '':
                    _ = 'localhost:50051'
                try:
                    host = _.split(':')[0]
                    port = _.split(':')[1]
                    while True:
                        try:
                            _ = input("输入用户名:")
                            if _ != '':
                                main(host, int(port), _)
                        except Exception as ex:
                            pass
                except Exception as ex:
                    print(f'链接错误: {ex}')
                    continue
        else:
            print('输入错误, 请重新输入')
            continue
