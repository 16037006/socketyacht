import socket
import json
import threading
import sys


class YachtClient:
    def __init__(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.player_id = None
        self.game_state = None
        self.current_dice = []
        self.rolls_left = 3

        # 입력 상태 관리
        self.input_state = "waiting"  # waiting, roll, reroll, category
        self.waiting_for_input = False

    def connect(self):
        try:
            self.socket.connect(('localhost', 8888))
            print("서버 접속 완료")
            threading.Thread(target=self.receive_messages, daemon=True).start()
            return True
        except Exception as e:
            print(f"접속 실패: {e}")
            return False

    def receive_messages(self):
        while True:
            try:
                data = self.socket.recv(1024).decode()
                if not data:
                    break

                message = json.loads(data)
                self.handle_message(message)

            except Exception as e:
                print(f"수신 오류: {e}")
                break

    def clear_input_buffer(self):
        """입력 버퍼 클리어"""
        try:
            import termios, tty
            sys.stdin.flush()
        except:
            pass

    def handle_message(self, message):
        if message["type"] == "player_id":
            self.player_id = message["data"]["id"]
            print(f"플레이어 {self.player_id + 1}로 게임 참여")

        elif message["type"] == "game_start":
            self.game_state = message["data"]
            print("\n=== 게임 시작 ===")
            self.show_game_status()
            self.update_input_state()

        elif message["type"] == "dice_result":
            data = message["data"]
            if data["player"] == self.player_id:
                self.current_dice = data["dice"]
                self.rolls_left = data["rolls_left"]
                print(f"\n주사위 결과: {self.current_dice}")
                print(f"남은 굴리기: {self.rolls_left}")

                if self.rolls_left > 0:
                    self.input_state = "reroll"
                    self.show_reroll_prompt()
                else:
                    self.input_state = "category"
                    self.show_category_prompt()

                self.waiting_for_input = True

        elif message["type"] == "turn_end":
            data = message["data"]
            self.game_state = data["game_state"]
            print(f"\n플레이어 {data['player'] + 1}: {data['category']} = {data['score']}점")
            self.show_game_status()
            self.update_input_state()

        elif message["type"] == "game_end":
            data = message["data"]
            print(f"\n=== 게임 종료 ===")
            print(f"승자: 플레이어 {data['winner'] + 1}")
            print(f"점수: {data['scores']}")
            self.input_state = "finished"
            self.waiting_for_input = False

    def update_input_state(self):
        """게임 상태에 따라 입력 상태 업데이트"""
        if not self.game_state:
            self.input_state = "waiting"
            self.waiting_for_input = False
            return

        current = self.game_state["current_player"]
        if current == self.player_id:
            self.input_state = "roll"
            self.waiting_for_input = True
            print("\n>>> 당신의 턴! 주사위를 굴리려면 'r' 입력: ", end='', flush=True)
        else:
            self.input_state = "waiting"
            self.waiting_for_input = False
            print(f"\n>>> 플레이어 {current + 1}의 턴 대기중...")

    def show_game_status(self):
        current = self.game_state["current_player"]
        print(f"\n현재 턴: 플레이어 {current + 1}")

        for i, player in enumerate(self.game_state["players"]):
            print(f"플레이어 {i + 1} 점수:")
            total = sum(player["scores"].values())
            print(f"  총점: {total}")
            for cat, score in player["scores"].items():
                print(f"  {cat}: {score}")

    def show_reroll_prompt(self):
        print("\n>>> 다시 굴릴 주사위 선택 (예: 1,3,5) 또는 엔터로 점수 선택: ", end='', flush=True)

    def show_category_prompt(self):
        print("\n점수 카테고리 선택:")
        categories = [
            "ones", "twos", "threes", "fours", "fives", "sixes",
            "three_of_kind", "four_of_kind", "full_house",
            "small_straight", "large_straight", "yacht", "chance"
        ]

        available = [c for c in categories if c not in self.game_state["players"][self.player_id]["scores"]]

        for i, cat in enumerate(available):
            score = self.preview_score(self.current_dice, cat)
            print(f"{i + 1}. {cat}: {score}점")

        print(">>> 선택 (숫자): ", end='', flush=True)

    def process_input(self, user_input):
        """입력 상태에 따른 처리"""
        user_input = user_input.strip()

        if self.input_state == "roll":
            if user_input.lower() == 'r':
                self.send_message({"type": "roll_dice", "data": {}})
                self.waiting_for_input = False
                print("주사위 굴리는 중...")
            else:
                print(">>> 주사위를 굴리려면 'r'을 입력하세요: ", end='', flush=True)

        elif self.input_state == "reroll":
            if user_input == "":
                # 엔터 - 점수 선택으로 이동
                self.input_state = "category"
                self.show_category_prompt()
            else:
                try:
                    indices = [int(x) - 1 for x in user_input.split(',')]
                    if all(0 <= i < 5 for i in indices):
                        self.send_message({"type": "roll_dice", "data": {"reroll": indices}})
                        self.waiting_for_input = False
                        print("선택된 주사위 다시 굴리는 중...")
                    else:
                        print(">>> 1-5 범위의 숫자를 입력하세요: ", end='', flush=True)
                except:
                    print(">>> 잘못된 형식입니다 (예: 1,3,5): ", end='', flush=True)

        elif self.input_state == "category":
            try:
                choice = int(user_input) - 1
                categories = [
                    "ones", "twos", "threes", "fours", "fives", "sixes",
                    "three_of_kind", "four_of_kind", "full_house",
                    "small_straight", "large_straight", "yacht", "chance"
                ]
                available = [c for c in categories if c not in self.game_state["players"][self.player_id]["scores"]]

                if 0 <= choice < len(available):
                    category = available[choice]
                    self.send_message({"type": "select_category", "data": {"category": category}})
                    self.waiting_for_input = False
                    print(f"{category} 선택됨")
                else:
                    print(f">>> 1-{len(available)} 범위의 숫자를 입력하세요: ", end='', flush=True)
            except:
                print(">>> 숫자를 입력하세요: ", end='', flush=True)

    def preview_score(self, dice, category):
        counts = [0] * 7
        for d in dice:
            counts[d] += 1

        if category in ["ones", "twos", "threes", "fours", "fives", "sixes"]:
            num = ["", "ones", "twos", "threes", "fours", "fives", "sixes"].index(category)
            return counts[num] * num
        elif category == "three_of_kind":
            return sum(dice) if max(counts) >= 3 else 0
        elif category == "four_of_kind":
            return sum(dice) if max(counts) >= 4 else 0
        elif category == "full_house":
            return 25 if (3 in counts and 2 in counts) else 0
        elif category == "small_straight":
            straights = [[1, 2, 3, 4], [2, 3, 4, 5], [3, 4, 5, 6]]
            for straight in straights:
                if all(counts[i] > 0 for i in straight):
                    return 30
            return 0
        elif category == "large_straight":
            if (counts[1:6] == [1, 1, 1, 1, 1]) or (counts[2:7] == [1, 1, 1, 1, 1]):
                return 40
            return 0
        elif category == "yacht":
            return 50 if max(counts) == 5 else 0
        elif category == "chance":
            return sum(dice)
        return 0

    def send_message(self, message):
        try:
            data = json.dumps(message).encode()
            self.socket.send(data)
        except Exception as e:
            print(f"전송 오류: {e}")

    def start(self):
        if self.connect():
            print("게임 시작 대기중...")

            try:
                while True:
                    if self.input_state == "finished":
                        break

                    # 입력 대기 상태일 때만 입력 받기
                    if self.waiting_for_input:
                        self.clear_input_buffer()
                        user_input = input()
                        self.process_input(user_input)
                    else:
                        # 대기 중일 때는 잠시 대기
                        import time
                        time.sleep(0.1)

            except KeyboardInterrupt:
                print("\n게임 종료")
            finally:
                self.socket.close()


if __name__ == "__main__":
    client = YachtClient()
    client.start()