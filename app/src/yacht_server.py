import socket
import json
import threading
import random
import time


class YachtServer:
    """야추 게임 서버 클래스.
    
    최대 2명의 플레이어가 참여할 수 있는 야추 게임 서버를 관리.
    소켓 통신을 통해 클라이언트와 연결하고 게임 로직을 처리.
    """
    
    def __init__(self):
        """서버 초기화.
        
        게임 상태, 플레이어 정보, 카테고리 목록을 초기화.
        """
        self.clients = []  # 연결된 클라이언트 소켓 목록
        self.game_state = {
            "current_player": 0,  # 현재 턴 플레이어 인덱스 (0 또는 1)
            "players": [
                {"name": "Player1", "scores": {}, "turn_data": {}},
                {"name": "Player2", "scores": {}, "turn_data": {}}
            ],
            "round": 1,  # 현재 라운드 (미사용)
            "game_over": False  # 게임 종료 플래그
        }
        # 야추 게임의 13개 카테고리 정의
        self.categories = [
            "ones", "twos", "threes", "fours", "fives", "sixes",
            "three_of_kind", "four_of_kind", "full_house",
            "small_straight", "large_straight", "yacht", "chance"
        ]

    def log(self, message: str) -> None:
        """시간 스탬프와 함께 로그 메시지 출력.
        
        Args:
            message: 출력할 로그 메시지
        """
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")

    def start_server(self) -> None:
        """서버 시작 및 클라이언트 연결 대기.
        
        포트 8888에서 최대 2명의 클라이언트 연결을 대기하고
        모든 플레이어가 접속하면 게임을 시작.
        """
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # 포트 재사용 허용
        server.bind(('localhost', 8888))  # 로컬호스트 8888번 포트에 바인딩
        server.listen(2)  # 최대 2개 연결 대기
        self.log("서버 시작 - 포트 8888")

        # 2명의 플레이어가 모두 접속할 때까지 대기
        while len(self.clients) < 2:
            client, addr = server.accept()
            self.clients.append(client)
            self.log(f"플레이어 {len(self.clients)} 접속: {addr}")
            # 각 클라이언트를 별도 스레드에서 처리
            threading.Thread(target=self.handle_client, args=(client, len(self.clients) - 1)).start()

        # 게임 시작 알림
        self.log("게임 시작!")
        self.broadcast({"type": "game_start", "data": self.game_state})

    def handle_client(self, client: socket.socket, player_id: int) -> None:
        """개별 클라이언트 연결 처리.
        
        Args:
            client: 클라이언트 소켓
            player_id: 플레이어 ID (0 또는 1)
        """
        # 클라이언트에게 플레이어 ID 전송
        welcome_msg = {"type": "player_id", "data": {"id": player_id}}
        client.send(json.dumps(welcome_msg).encode())
        self.log(f"플레이어 {player_id + 1}에게 ID 할당")

        while True:
            try:
                data = client.recv(1024).decode()  # 1KB 버퍼로 데이터 수신
                if not data:
                    break

                message = json.loads(data)
                self.log(f"플레이어 {player_id + 1}에서 수신: {message['type']}")
                self.process_message(message, player_id)

            except Exception as e:
                self.log(f"클라이언트 {player_id + 1} 오류: {e}")
                break

        client.close()
        self.log(f"플레이어 {player_id + 1} 연결 종료")

    def process_message(self, message: dict, player_id: int) -> None:
        """클라이언트 메시지 처리.
        
        Args:
            message: 클라이언트에서 받은 메시지 딕셔너리
            player_id: 메시지를 보낸 플레이어 ID
        """
        if message["type"] == "roll_dice":
            # 현재 턴 플레이어만 주사위를 굴릴 수 있음
            if player_id == self.game_state["current_player"]:
                current_turn = self.game_state["players"][player_id]["turn_data"]

                if "dice" not in current_turn:
                    # 첫 굴리기 - 5개 주사위 모두 굴림
                    dice = [random.randint(1, 6) for _ in range(5)]  # 1-6 랜덤 값 5개 생성
                    current_turn["dice"] = dice
                    current_turn["rolls_left"] = 2  # 최대 3번까지 굴릴 수 있으므로 2번 남음
                    self.log(f"플레이어 {player_id + 1} 첫 굴리기: {dice}")
                else:
                    # 재굴리기 - 선택된 주사위만 다시 굴림
                    reroll_indices = message["data"].get("reroll", [])
                    dice = current_turn["dice"].copy()
                    old_dice = dice.copy()
                    # 선택된 인덱스의 주사위만 새로 굴림
                    for i in reroll_indices:
                        if 0 <= i < 5:  # 유효한 인덱스 범위 체크 (0-4)
                            dice[i] = random.randint(1, 6)
                    current_turn["dice"] = dice
                    current_turn["rolls_left"] -= 1
                    self.log(f"플레이어 {player_id + 1} 재굴리기 {reroll_indices}: {old_dice} -> {dice}")

                self.broadcast({
                    "type": "dice_result",
                    "data": {
                        "dice": current_turn["dice"],
                        "player": player_id,
                        "rolls_left": current_turn["rolls_left"]
                    }
                })

        elif message["type"] == "select_category":
            # 현재 턴 플레이어만 카테고리를 선택할 수 있음
            if player_id == self.game_state["current_player"]:
                category = message["data"]["category"]
                dice = self.game_state["players"][player_id]["turn_data"]["dice"]
                score = self.calculate_score(dice, category)

                # 선택된 카테고리에 점수 기록
                self.game_state["players"][player_id]["scores"][category] = score
                self.game_state["players"][player_id]["turn_data"] = {}  # 턴 데이터 초기화

                self.log(f"플레이어 {player_id + 1} 점수 기록: {category} = {score}")

                # 턴 변경 - 0과 1 사이를 토글
                self.game_state["current_player"] = 1 - self.game_state["current_player"]

                # 게임 종료 체크 - 각 플레이어가 13개 카테고리를 모두 채웠는지 확인
                if len(self.game_state["players"][player_id]["scores"]) == 13:
                    if len(self.game_state["players"][1 - player_id]["scores"]) == 13:
                        self.end_game()
                        return

                self.broadcast({
                    "type": "turn_end",
                    "data": {
                        "score": score,
                        "category": category,
                        "player": player_id,
                        "game_state": self.game_state
                    }
                })

    def calculate_score(self, dice: list, category: str) -> int:
        """주사위 결과와 카테고리에 따른 점수 계산.
        
        Args:
            dice: 5개 주사위 값의 리스트
            category: 점수를 계산할 카테고리명
            
        Returns:
            계산된 점수
        """
        # 각 숫자(1-6)의 개수를 세기 위한 배열 (인덱스 0은 미사용)
        counts = [0] * 7
        for d in dice:
            counts[d] += 1

        # 숫자 카테고리 (1-6): 해당 숫자의 개수 × 숫자 값
        if category in ["ones", "twos", "threes", "fours", "fives", "sixes"]:
            num = ["", "ones", "twos", "threes", "fours", "fives", "sixes"].index(category)
            return counts[num] * num

        # 3 of a kind: 같은 숫자 3개 이상 시 모든 주사위 합
        elif category == "three_of_kind":
            return sum(dice) if max(counts) >= 3 else 0
        # 4 of a kind: 같은 숫자 4개 이상 시 모든 주사위 합
        elif category == "four_of_kind":
            return sum(dice) if max(counts) >= 4 else 0
        # Full house: 3개 + 2개 조합 시 25점 고정
        elif category == "full_house":
            return 25 if (3 in counts and 2 in counts) else 0
        # Small straight: 연속된 4개 숫자 시 30점 고정
        elif category == "small_straight":
            straights = [[1, 2, 3, 4], [2, 3, 4, 5], [3, 4, 5, 6]]  # 가능한 연속 4개 조합
            for straight in straights:
                if all(counts[i] > 0 for i in straight):
                    return 30
            return 0
        # Large straight: 연속된 5개 숫자 시 40점 고정
        elif category == "large_straight":
            # (1,2,3,4,5) 또는 (2,3,4,5,6) 패턴 체크
            if (counts[1:6] == [1, 1, 1, 1, 1]) or (counts[2:7] == [1, 1, 1, 1, 1]):
                return 40
            return 0
        # Yacht: 같은 숫자 5개 시 50점 고정
        elif category == "yacht":
            return 50 if max(counts) == 5 else 0
        # Chance: 모든 주사위 합
        elif category == "chance":
            return sum(dice)

        return 0

    def end_game(self) -> None:
        """게임 종료 처리.
        
        각 플레이어의 총점을 계산하고 승자를 결정한 후
        모든 클라이언트에게 게임 종료 메시지 전송.
        """
        scores = [sum(p["scores"].values()) for p in self.game_state["players"]]
        winner = 0 if scores[0] > scores[1] else 1  # 더 높은 점수의 플레이어가 승자

        self.broadcast({
            "type": "game_end",
            "data": {
                "winner": winner,
                "scores": scores
            }
        })

    def broadcast(self, message: dict) -> None:
        """모든 연결된 클라이언트에게 메시지 브로드캐스트.
        
        Args:
            message: 전송할 메시지 딕셔너리
        """
        data = json.dumps(message).encode()
        for client in self.clients:
            try:
                client.send(data)
            except:
                # 전송 실패 시 무시 (연결이 끊어진 클라이언트)
                pass


if __name__ == "__main__":
    server = YachtServer()
    server.start_server()