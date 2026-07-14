from enum import Enum
from typing import Dict, List, Optional
import math

# 최상위 기본 노드
class Node:
    def __init__(self, node_id, name, x, y, floor, category):
        self.node_id = node_id
        self.name = name
        self.x = x
        self.y = y
        self.floor = floor
        self.category = category
        self.stay_time = 0  # 모든 노드의 초기 소요 시간은 무조건 0으로 세팅

    def update_stay_time(self, congestion_func=None, current_time=None):
        self.stay_time = 0

    def __repr__(self):
        return f"[{self.category}] {self.name} (소요시간: {self.stay_time}초)"


# 1. 교실 객체 (대기 시간 없음 -> 0 고정)
class ClassroomNode(Node):
    def __init__(self, node_id, name, x, y, floor):
        super().__init__(node_id, name, x, y, floor, category="교실")


# 2. 계단 객체 (대기 시간 없음 -> 0 고정)
class StairsNode(Node):
    def __init__(self, node_id, name, x, y, floor, stair_group, base_time_per_floor=15.0):
        super().__init__(node_id, name, x, y, floor, category="계단")
        self.stair_group = stair_group
        self.base_time_per_floor = base_time_per_floor

    def calculate_stair_time(self, target_floor):
        """
        [수정] 시뮬레이터 내 지연 함수 제외 요청에 따라 혼잡도 계산 로직 제거
        층간 이동에 걸리는 순수 기본 소요 시간만 반환합니다.
        """
        floor_diff = abs(target_floor - self.floor)
        return floor_diff * self.base_time_per_floor


# 3. 홈베이스 객체
class HomebaseNode(Node):
    def __init__(self, node_id, name, x, y, floor):
        super().__init__(node_id, name, x, y, floor, category="홈베이스")


# --- 대기 시간이 발생하는 노드들을 위한 부모 클래스 ---
class WaitableNode(Node):
    def __init__(self, node_id, name, x, y, floor, category, base_wait_time, custom_congestion_func=None):
        super().__init__(node_id, name, x, y, floor, category)
        self.base_wait_time = base_wait_time
        self.custom_congestion_func = custom_congestion_func  # 객체 생성 시점에 저장됨

    def get_stay_time(self, current_time=None):
        """
        [수정] 시뮬레이터에서 공통으로 넘겨받던 global_congestion_func 매개변수 완전히 제외.
        오직 객체 생성 시 주입받은 자신만의 전용 함수(custom_congestion_func)만 판별하여 적용합니다.
        """
        if self.custom_congestion_func:
            return self.custom_congestion_func(self.base_wait_time, current_time)
        return self.base_wait_time


# [수정] 객체 생성 시점에 custom_congestion_func를 직접 넘겨줄 수 있도록 매개변수 추가
class RestroomNode(WaitableNode):
    def __init__(self, node_id, name, x, y, floor, base_wait_time, custom_congestion_func=None):
        super().__init__(node_id, name, x, y, floor, category="화장실", base_wait_time=base_wait_time, custom_congestion_func=custom_congestion_func)


class StoreNode(WaitableNode):
    def __init__(self, node_id, name, x, y, floor, base_wait_time, custom_congestion_func=None):
        super().__init__(node_id, name, x, y, floor, category="매점", base_wait_time=base_wait_time, custom_congestion_func=custom_congestion_func)


# 복도를 대신할 교차점 노드
class IntersectionNode(Node):
    def __init__(self, node_id, name, x, y, floor):
        super().__init__(node_id, name, x, y, floor, category="교차점")


class SchoolMap:
    def __init__(self):
        self.nodes = {} 
        self.adjacency_list = {} 

    def add_node(self, node):
        self.nodes[node.node_id] = node
        self.adjacency_list[node.node_id] = [] 

    def connect_nodes(self, node_id_1, node_id_2):
        if node_id_1 in self.nodes and node_id_2 in self.nodes:
            self.adjacency_list[node_id_1].append(node_id_2)
            self.adjacency_list[node_id_2].append(node_id_1)
        else:
            raise ValueError("존재하지 않는 노드를 연결하려고 합니다.")
        

class TimeManager:
    def __init__(self, time_slot_name: str, max_duration_sec: int = 600, walking_speed_m_s: float = 1.0):
        self.current_time_slot = time_slot_name
        self.max_duration_sec = max_duration_sec
        self.walking_speed = walking_speed_m_s  
        self.elapsed_sec = 0.0        

    def add_raw_time(self, seconds: float):
        if seconds < 0:
            raise ValueError("소요 시간은 음수가 될 수 없습니다.")
        self.elapsed_sec += seconds

    def add_node_stay_time(self, node, congestion_func=None):
        """
        노드에서 즉석으로 대기 시간을 계산하여 누적합니다.
        파라미터 타입을 숫자로 통일하기 위해 self.elapsed_sec를 넘겨줍니다.
        """
        if hasattr(node, 'get_stay_time'):
            # [수정] current_time 변수에 문자열 대신 숫자인 self.elapsed_sec를 주입합니다.
            stay_time = node.get_stay_time(
                congestion_func=congestion_func, 
                current_time=self.elapsed_sec  
            )
            self.elapsed_sec += stay_time
        elif hasattr(node, 'stay_time'):
            self.elapsed_sec += node.stay_time
        else:
            raise AttributeError(f"{node} 객체에 시간 계산 속성이 없습니다.")
                
    def add_walking_travel_time(self, start_node, end_node):
        """
        [수정] 이동 중 복도 혼잡도를 적용하던 로직 및 외부 지연 함수 매개변수를 완전히 제외했습니다.
        """
        if start_node.floor != end_node.floor:
            raise ValueError(f"오류: {start_node.name}과 {end_node.name}은 층이 달라 걸어서 이동할 수 없습니다.")

        distance = math.hypot(start_node.x - end_node.x, start_node.y - end_node.y)
        base_time = distance / self.walking_speed
        self.elapsed_sec += base_time

    def add_stair_travel_time(self, stair_node, target_floor):
        """
        [수정] 계단 이동 시 혼잡도를 적용하던 로직 및 외부 지연 함수 매개변수를 완전히 제외했습니다.
        """
        if hasattr(stair_node, 'calculate_stair_time'):
            travel_time = stair_node.calculate_stair_time(target_floor=target_floor)
            self.elapsed_sec += travel_time
        else:
            raise AttributeError(f"{stair_node} 객체에 calculate_stair_time 속성이 없습니다.")
        
    def get_remaining_time(self) -> float:
        return max(0.0, self.max_duration_sec - self.elapsed_sec)

    def is_time_over(self) -> bool:
        return self.elapsed_sec > self.max_duration_sec

    def reset(self):
        self.elapsed_sec = 0.0
        
    def __repr__(self):
        minutes = int(self.elapsed_sec // 60)
        seconds = int(self.elapsed_sec % 60)
        return f"[{self.current_time_slot}] 누적: {minutes}분 {seconds}초 / 남은 시간: {int(self.get_remaining_time())}초"
    

def simulate_student_movement(path: list, destination_node, time_manager):
    """
    [수정] 시뮬레이터 구동 함수에서 혼잡도 관련 매개변수(congestion_func)를 완전히 제외했습니다.
    """
    print(f"\n🏃‍♂️ 출발! 최종 목적지: {destination_node.name}")
    print("-" * 40)

    # 1. 경로를 따라 이동 (순수 물리 이동 시간만 누적)
    for i in range(len(path) - 1):
        current_node = path[i]
        next_node = path[i + 1]
        
        # 층간 이동 (계단)
        if current_node.floor != next_node.floor and hasattr(current_node, 'calculate_stair_time'):
             time_manager.add_stair_travel_time(current_node, next_node.floor)
             print(f"[{time_manager.elapsed_sec:5.1f}초] {current_node.name}에서 {next_node.floor}층으로 계단 이동")
        
        # 같은 층 이동 (걷기)
        else:
             time_manager.add_walking_travel_time(current_node, next_node)
             print(f"[{time_manager.elapsed_sec:5.1f}초] {current_node.name} ➡️ {next_node.name} 걷는 중...")

    # 2. 최종 목적지 도착 시 처리 (도착 노드 내부의 전용 대기 수식에 따라 시간 산정)
    print(f"[{time_manager.elapsed_sec:5.1f}초] 🏁 {destination_node.name} 도착!")
    time_manager.add_node_stay_time(destination_node)
    
    print("-" * 40)
    print(f"✅ 최종 소요 시간: {time_manager.elapsed_sec:.1f}초")
    print(f"✅ 쉬는 시간 상태: 남은 시간 {time_manager.get_remaining_time():.1f}초")
  

# ==========================================
# 장소(Node) 체류용 지연 함수 정의
# ==========================================
def store_stay_logic(base_wait_time, time_slot):
    if "8교시" in time_slot:
        return base_wait_time * (1 + 2.200 * (1.0 ** 2))
    return base_wait_time

def restroom_stay_logic(base_wait_time, time_slot):
    if "8교시" in time_slot:
        return base_wait_time * (1 + 0.100 * 1.0)
    return base_wait_time


if __name__=="__main__":
    school_map = SchoolMap()

    # --- 1층 노드 세팅 ---
    s1 = StairsNode(node_id="S1", name="회전 계단(1F)", x=0, y=-1, floor=1, stair_group="Side")
    c1 = ClassroomNode(node_id="C1", name="체육관", x=0, y=15, floor=1)

    # --- 3층 노드 세팅 ---
    s31 = StairsNode(node_id="S31", name='중앙 계단(3F)', x=5, y=5, floor=3, stair_group="Center")
    s32 = StairsNode(node_id="S32", name='회전 계단(3F)', x=0, y=-1, floor=3, stair_group="Side")
    i3 = IntersectionNode(node_id="I3", name="3층 중앙 복도", x=0, y=0, floor=3)
    
    # [수정] 객체 생성 시점에 매개변수로 전용 지연 함수(logic)를 바로 주입합니다.
    r3 = RestroomNode(node_id="R3", name="3층 화장실", x=-13, y=0, floor=3, base_wait_time=30.0, custom_congestion_func=restroom_stay_logic)
    m3 = StoreNode(node_id="M3", name="3층 매점", x=0, y=5, floor=3, base_wait_time=100.0, custom_congestion_func=store_stay_logic)
    
    c3 = ClassroomNode(node_id="C3", name="3학년 8반", x=-10, y=0, floor=3)
    h3 = HomebaseNode(node_id="H3", name='홈베이스', x=0, y=-12, floor=3)
    
    # --- 4층 노드 세팅 ---

    s41= StairsNode(node_id="S41", name='중앙 계단(4F)', x=5, y=9, floor=4, stair_group="Center")
    s42= StairsNode(node_id="S42", name='회전 계단(4F)', x=0, y=-1, floor=4, stair_group="Side")
    i4 = IntersectionNode(node_id="I4", name="4층 중앙 복도", x=0, y=0, floor=4)
    r41 = RestroomNode(node_id="R41", name="4층 화장실1", x=0, y=9, floor=4, base_wait_time=30.0)
    r42 = RestroomNode(node_id="R42", name="4층 화장실2", x=-13, y=0, floor=4, base_wait_time=30.0)

    # 맵에 노드 등록 및 연결 (생략 없이 유지)
    for node in [s1, c1, s31, s32, i3, r3, m3, c3, h3]:
        school_map.add_node(node)

    school_map.connect_nodes("S1", "C1")
    school_map.connect_nodes("I3", "S31")
    school_map.connect_nodes("I3", "C3")
    school_map.connect_nodes("I3", "M3")
    school_map.connect_nodes("I3", "S32")
    school_map.connect_nodes("C3", "R3")
    school_map.connect_nodes("S32", "H3")

    # 시뮬레이션 환경 세팅 (8교시로 가정하여 지연 함수 발동 테스트)
    time_mgr = TimeManager("8교시", max_duration_sec=600, walking_speed_m_s=1.5)

    # 시나리오: 체육관(1F)에서 출발해 3층 매점(M3)으로 이동하는 가상 경로
    sample_path = [c1, s1, s32, i3, m3]

    # [수정] 호출 시 시뮬레이터에 불필요한 공통 혼잡도 함수를 인자로 던지지 않습니다.
    simulate_student_movement(
        path=sample_path, 
        destination_node=m3, 
        time_manager=time_mgr
    )