import socket
import json
import threading
import sys


class YachtClient:
    """야추 게임 클라이언트 클래스.
    
    서버에 연결하여 야추 게임을 플레이하는 클라이언트.
    소켓 통신을 통해 서버와 메시지를 주고받고 사용자 입력을 처리.
    """
    
    def __init__(self):
        """클라이언트 초기화.
        
        소켓, 게임 상태, 입력 상태 관리 변수들을 초기화.
        """
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.player_id = None  # 서버에서 할당받을 플레이어 ID (0 또는 1)
        self.game_state = None  # 서버에서 받은 게임 상태
        self.current_dice = []  # 현재 턴의 주사위 결과
        self.rolls_left = 3  # 남은 굴리기 횟수 (최대 3번)

        # 입력 상태 관리 - 현재 어떤 입력을 기다리는지 추적
        self.input_state = "waiting"  # waiting, roll, reroll, category, finished
        self.waiting_for_input = False  # 사용자 입력 대기 플래그

    def connect(self) -> bool:
        """서버에 연결 시도.
        
        Returns:
            연결 성공 시 True, 실패 시 False
        """
        try:
            self.socket.connect(('localhost', 8888))  # 로컬호스트 8888번 포트로 연결
            print("서버 접속 완료")
            # 메시지 수신을 별도 스레드에서 처리 (daemon으로 설정하여 메인 종료 시 함께 종료)
            threading.Thread(target=self.receive_messages, daemon=True).start()
            return True
        except Exception as e:
            print(f"접속 실패: {e}")
            return False

    def receive_messages(self) -> None:
        """서버로부터 메시지 수신 처리.
        
        별도 스레드에서 실행되어 서버 메시지를 지속적으로 수신.
        """
        while True:
            try:
                data = self.socket.recv(1024).decode()  # 1KB 버퍼로 데이터 수신
                if not data:
                    break

                message = json.loads(data)
                self.handle_message(message)

            except Exception as e:
                print(f"수신 오류: {e}")
                break

    def clear_input_buffer(self) -> None:
        """입력 버퍼 클리어.
        
        터미널 입력 버퍼를 클리어하여 이전 입력이 남아있지 않도록 처리.
        Unix/Linux 시스템에서만 동작.
        """
        try:
            import termios, tty
            sys.stdin.flush()
        except:
            # Windows나 termios 미지원 시스템에서는 무시
            pass

    def handle_message(self, message: dict) -> None:
        """서버에서 받은 메시지 처리.
        
        Args:
            message: 서버에서 받은 메시지 딕셔너리
        """
        if message["type"] == "player_id":
            # 서버에서 할당한 플레이어 ID 저장
            self.player_id = message["data"]["id"]
            print(f"플레이어 {self.player_id + 1}로 게임 참여")

        elif message["type"] == "game_start":
            # 게임 시작 - 초기 게임 상태 수신
            self.game_state = message["data"]
            print("\n=== 게임 시작 ===")
            self.show_game_status()
            self.update_input_state()

        elif message["type"] == "dice_result":
            # 주사위 굴리기 결과 처리
            data = message["data"]
            if data["player"] == self.player_id:  # 본인의 주사위 결과만 처리
                self.current_dice = data["dice"]
                self.rolls_left = data["rolls_left"]
                print(f"\n주사위 결과: {self.current_dice}")
                print(f"남은 굴리기: {self.rolls_left}")

                # 굴리기 횟수에 따라 다음 입력 상태 결정
                if self.rolls_left > 0:
                    self.input_state = "reroll"  # 재굴리기 또는 점수 선택 가능
                    self.show_reroll_prompt()
                else:
                    self.input_state = "category"  # 점수 선택만 가능
                    self.show_category_prompt()

                self.waiting_for_input = True

        elif message["type"] == "turn_end":
            # 턴 종료 - 점수 기록 및 게임 상태 업데이트
            data = message["data"]
            self.game_state = data["game_state"]
            print(f"\n플레이어 {data['player'] + 1}: {data['category']} = {data['score']}점")
            self.show_game_status()
            self.update_input_state()

        elif message["type"] == "game_end":
            # 게임 종료 - 승자 및 최종 점수 표시
            data = message["data"]
            print(f"\n=== 게임 종료 ===")
            print(f"승자: 플레이어 {data['winner'] + 1}")
            print(f"점수: {data['scores']}")
            self.input_state = "finished"
            self.waiting_for_input = False

    def update_input_state(self) -> None:
        """게임 상태에 따라 입력 상태 업데이트.
        
        현재 턴 플레이어인지 확인하고 적절한 프롬프트 표시.
        """
        if not self.game_state:
            self.input_state = "waiting"
            self.waiting_for_input = False
            return

        current = self.game_state["current_player"]
        if current == self.player_id:
            # 본인 턴 - 주사위 굴리기 대기
            self.input_state = "roll"
            self.waiting_for_input = True
            print("\n>>> 당신의 턴! 주사위를 굴리려면 'r' 입력: ", end='', flush=True)
        else:
            # 상대방 턴 - 대기 상태
            self.input_state = "waiting"
            self.waiting_for_input = False
            print(f"\n>>> 플레이어 {current + 1}의 턴 대기중...")

    def show_game_status(self) -> None:
        """현재 게임 상태 표시.
        
        현재 턴 플레이어와 각 플레이어의 점수를 출력.
        """
        current = self.game_state["current_player"]
        print(f"\n현재 턴: 플레이어 {current + 1}")

        for i, player in enumerate(self.game_state["players"]):
            print(f"플레이어 {i + 1} 점수:")
            total = sum(player["scores"].values())
            print(f"  총점: {total}")
            # 기록된 카테고리별 점수 표시
            for cat, score in player["scores"].items():
                print(f"  {cat}: {score}")

    def show_reroll_prompt(self) -> None:
        """재굴리기 선택 프롬프트 표시.
        
        사용자가 다시 굴릴 주사위를 선택하거나 점수 선택으로 넘어갈 수 있음을 안내.
        """
        print("\n>>> 다시 굴릴 주사위 선택 (예: 1,3,5) 또는 엔터로 점수 선택: ", end='', flush=True)

    def show_category_prompt(self) -> None:
        """점수 카테고리 선택 프롬프트 표시.
        
        아직 선택하지 않은 카테고리 목록과 예상 점수를 표시.
        """
        print("\n점수 카테고리 선택:")
        # 야추 게임의 13개 카테고리 정의
        categories = [
            "ones", "twos", "threes", "fours", "fives", "sixes",
            "three_of_kind", "four_of_kind", "full_house",
            "small_straight", "large_straight", "yacht", "chance"
        ]

        # 아직 선택하지 않은 카테고리만 표시
        available = [c for c in categories if c not in self.game_state["players"][self.player_id]["scores"]]

        for i, cat in enumerate(available):
            score = self.preview_score(self.current_dice, cat)
            print(f"{i + 1}. {cat}: {score}점")

        print(">>> 선택 (숫자): ", end='', flush=True)

    def process_input(self, user_input: str) -> None:
        """입력 상태에 따른 사용자 입력 처리.
        
        Args:
            user_input: 사용자가 입력한 문자열
        """
        user_input = user_input.strip()

        if self.input_state == "roll":
            # 주사위 굴리기 상태
            if user_input.lower() == 'r':
                self.send_message({"type": "roll_dice", "data": {}})
                self.waiting_for_input = False
                print("주사위 굴리는 중...")
            else:
                print(">>> 주사위를 굴리려면 'r'을 입력하세요: ", end='', flush=True)

        elif self.input_state == "reroll":
            # 재굴리기 선택 상태
            if user_input == "":
                # 엔터 입력 - 점수 선택으로 이동
                self.input_state = "category"
                self.show_category_prompt()
            else:
                try:
                    # 콤마로 구분된 주사위 인덱스 파싱 (1-based를 0-based로 변환)
                    indices = [int(x) - 1 for x in user_input.split(',')]
                    if all(0 <= i < 5 for i in indices):  # 유효한 인덱스 범위 체크 (0-4)
                        self.send_message({"type": "roll_dice", "data": {"reroll": indices}})
                        self.waiting_for_input = False
                        print("선택된 주사위 다시 굴리는 중...")
                    else:
                        print(">>> 1-5 범위의 숫자를 입력하세요: ", end='', flush=True)
                except:
                    print(">>> 잘못된 형식입니다 (예: 1,3,5): ", end='', flush=True)

        elif self.input_state == "category":
            # 카테고리 선택 상태
            try:
                choice = int(user_input) - 1  # 1-based 입력을 0-based로 변환
                categories = [
                    "ones", "twos", "threes", "fours", "fives", "sixes",
                    "three_of_kind", "four_of_kind", "full_house",
                    "small_straight", "large_straight", "yacht", "chance"
                ]
                # 아직 선택하지 않은 카테고리만 필터링
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

    def preview_score(self, dice: list, category: str) -> int:
        """특정 카테고리에서 현재 주사위로 얻을 수 있는 점수 미리보기.
        
        Args:
            dice: 5개 주사위 값의 리스트
            category: 점수를 계산할 카테고리명
            
        Returns:
            해당 카테고리에서 얻을 수 있는 점수
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

    def send_message(self, message: dict) -> None:
        """서버에 메시지 전송.
        
        Args:
            message: 전송할 메시지 딕셔너리
        """
        try:
            data = json.dumps(message).encode()
            self.socket.send(data)
        except Exception as e:
            print(f"전송 오류: {e}")

    def start(self) -> None:
        """클라이언트 시작.
        
        서버에 연결하고 메인 입력 루프를 실행.
        사용자 입력을 받아 적절히 처리하고 게임이 끝날 때까지 실행.
        """
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
                        time.sleep(0.1)  # 100ms 대기

            except KeyboardInterrupt:
                print("\n게임 종료")
            finally:
                self.socket.close()


if __name__ == "__main__":
    client = YachtClient()
    client.start()