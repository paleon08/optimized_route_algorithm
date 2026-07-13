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
        """
        기본 노드는 대기 시간이 없으므로, 어떤 함수가 들어와도 0을 유지합니다.
        """
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
        # 한 층을 이동하는 데 걸리는 기본 시간 (상수, 예: 15초)
        self.base_time_per_floor = base_time_per_floor

    def calculate_stair_time(self, target_floor, congestion_func=None, current_time=None):
        """
        이동할 층수를 기반으로 기본 소요 시간을 구하고, 혼잡도 함수를 적용합니다.
        (계단은 머무는 곳이 아니라 통과하는 곳이므로 stay_time 대신 별도 반환값 사용)
        """
        floor_diff = abs(target_floor - self.floor)
        base_time = floor_diff * self.base_time_per_floor
        
        # 화장실/매점의 stay_time을 구하던 방식과 동일하게 혼잡도 함수를 적용
        if congestion_func:
            return congestion_func(base_time, current_time)
        return base_time

#홈베이스
class HomebaseNode(Node):
    def __init__(self, node_id, name, x, y, floor):
        super().__init__(node_id, name, x, y, floor, category="홈베이스")


# --- 대기 시간이 발생하는 특정 노드들 ---

# --- 대기 시간이 발생하는 노드들을 위한 부모 클래스 도입 (중복 제거) ---

class WaitableNode(Node):
    # 1. 생성자 파라미터에 custom_congestion_func 추가 (기본값은 None)
    def __init__(self, node_id, name, x, y, floor, category, base_wait_time, custom_congestion_func=None):
        super().__init__(node_id, name, x, y, floor, category)
        self.base_wait_time = base_wait_time
        self.custom_congestion_func = custom_congestion_func  # 내부에 저장

    def get_stay_time(self, global_congestion_func=None, current_time=None):
        """
        우선순위를 두어 혼잡도 함수를 적용합니다.
        """
        # 1순위: 자기 자신만의 전용 함수가 지정되어 있다면 그것을 최우선으로 사용!
        if self.custom_congestion_func:
            return self.custom_congestion_func(self.base_wait_time, current_time)
        
        # 2순위: 전용 함수는 없지만, TimeManager에서 넘겨준 공통 함수가 있다면 그것을 사용
        elif global_congestion_func:
            return global_congestion_func(self.base_wait_time, current_time)
        
        # 3순위: 둘 다 없으면 원래 지정된 기본 대기 시간 반환
        return self.base_wait_time

# 화장실과 매점은 이제 카테고리만 넘겨주면 끝납니다.
class RestroomNode(WaitableNode):
    def __init__(self, node_id, name, x, y, floor, base_wait_time):
        super().__init__(node_id, name, x, y, floor, category="화장실", base_wait_time=base_wait_time)

class StoreNode(WaitableNode):
    def __init__(self, node_id, name, x, y, floor, base_wait_time):
        super().__init__(node_id, name, x, y, floor, category="매점", base_wait_time=base_wait_time)

# 복도를 대신할 교차점 노드
class IntersectionNode(Node):
    def __init__(self, node_id, name, x, y, floor):
        super().__init__(node_id, name, x, y, floor, category="교차점")

class SchoolMap:
    def __init__(self):
        self.nodes = {} 
        self.adjacency_list = {} # 딕셔너리를 활용해 어떤 노드가 어디랑 연결되어 있는지 기록

    def add_node(self, node):
        self.nodes[node.node_id] = node
        self.adjacency_list[node.node_id] = [] # 노드가 추가될 때 빈 연결 리스트 생성

    def connect_nodes(self, node_id_1, node_id_2):
        """
        두 노드(예: 교실문 앞 교차점 ↔ 복도 끝 교차점)를 연결하여 길을 만듭니다.
        (양방향 연결)
        """
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

    # 1. 단순 초 단위 누적 (수동)
    def add_raw_time(self, seconds: float):
        if seconds < 0:
            raise ValueError("소요 시간은 음수가 될 수 없습니다.")
        self.elapsed_sec += seconds

    # 2. 장소(Node) 연동: 대기 시간/업무 시간 처리
    def add_node_stay_time(self, node, congestion_func=None):
        """
        노드에서 즉석으로 대기 시간을 계산하여 누적합니다.
        """
        # WaitableNode처럼 get_stay_time이 구현된 경우
        if hasattr(node, 'get_stay_time'):
            stay_time = node.get_stay_time(
                congestion_func=congestion_func, 
                current_time=self.elapsed_sec
            )
            self.elapsed_sec += stay_time
        # 교실처럼 대기 시간이 아예 없는 기본 노드 처리
        elif hasattr(node, 'stay_time'):
            self.elapsed_sec += node.stay_time
        else:
            raise AttributeError(f"{node} 객체에 시간 계산 속성이 없습니다.")

    # 3. [수정됨] 걷기 이동 시간 자동 계산 (선분 객체 대신 노드 간 거리 계산)
    def add_walking_travel_time(self, start_node, end_node, congestion_func=None):
        """
        같은 층에 있는 두 노드 사이의 직선 거리를 계산하여 소요 시간을 누적합니다.
        """
        # 논리적 오류 방지: 층이 다르면 걸어서 바로 갈 수 없음
        if start_node.floor != end_node.floor:
            raise ValueError(f"오류: {start_node.name}({start_node.floor}F)과 {end_node.name}({end_node.floor}F)은 층이 달라 걸어서 이동할 수 없습니다. 계단을 이용해야 합니다.")

        # 좌표를 이용한 실제 거리 계산
        distance = math.hypot(start_node.x - end_node.x, start_node.y - end_node.y)
        
        # 기본 소요 시간 = 거리 / 속력
        base_time = distance / self.walking_speed

        if congestion_func:
            # 이동 중 복도 혼잡도 적용
            travel_time = congestion_func(base_time, self.elapsed_sec)
            self.elapsed_sec += travel_time
        else:
            self.elapsed_sec += base_time

    # 4. 계단(StairsNode) 연동: 층간 이동 시간 자동 계산 (혼잡도 반영)
    def add_stair_travel_time(self, stair_node, target_floor, congestion_func=None):
        """
        계단을 이용한 층간 이동 시 발생하는 시간을 누적합니다.
        """
        if hasattr(stair_node, 'calculate_stair_time'):
            travel_time = stair_node.calculate_stair_time(
                target_floor=target_floor,
                congestion_func=congestion_func,
                current_time=self.elapsed_sec
            )
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
    
def simulate_student_movement(path: list, destination_node, time_manager, congestion_func=None):
    """
    주어진 경로(path)를 따라 학생이 이동하는 과정을 시간과 함께 시뮬레이션합니다.
    """
    print(f"\n🏃‍♂️ 출발! 최종 목적지: {destination_node.name}")
    print("-" * 40)

    # 1. 경로를 따라 이동 (경유지 처리)
    for i in range(len(path) - 1):
        current_node = path[i]
        next_node = path[i + 1]
        
        # 층간 이동 (계단)
        if current_node.floor != next_node.floor and hasattr(current_node, 'calculate_stair_time'):
             time_manager.add_stair_travel_time(current_node, next_node.floor, congestion_func)
             print(f"[{time_manager.elapsed_sec:5.1f}초] {current_node.name}에서 {next_node.floor}층으로 계단 이동")
        
        # 같은 층 이동 (걷기)
        else:
             time_manager.add_walking_travel_time(current_node, next_node, congestion_func)
             print(f"[{time_manager.elapsed_sec:5.1f}초] {current_node.name} ➡️ {next_node.name} 걷는 중...")

    # 2. 최종 목적지 도착 시 처리 (체류/대기 시간 적용)
    print(f"[{time_manager.elapsed_sec:5.1f}초] 🏁 {destination_node.name} 도착!")
    time_manager.add_node_stay_time(destination_node, congestion_func)
    
    print("-" * 40)
    print(f"✅ 최종 소요 시간: {time_manager.elapsed_sec:.1f}초")
    print(f"✅ 쉬는 시간 상태: 남은 시간 {time_manager.get_remaining_time():.1f}초")
  

if __name__=="__main__":
    # ==========================================
    # 1. 학교 지도(환경) 생성
    # ==========================================
    school_map = SchoolMap()

    # --- 1층 노드 세팅 ---
    # 좌표 기준: x축(가로), y축(세로) - 단위는 편의상 미터(m)로 가정
    i1 = IntersectionNode(node_id="I1", name="1층 중앙 복도", x=0, y=0, floor=1)
    r1 = RestroomNode(node_id="R1", name="1층 화장실", x=15, y=0, floor=1, base_wait_time=30.0)
    s1 = StairsNode(node_id="S1", name="중앙 계단(1F)", x=0, y=10, floor=1, stair_group="Center")

    # --- 2층 노드 세팅 ---
    s2 = StairsNode(node_id="S2", name="중앙 계단(2F)", x=0, y=10, floor=2, stair_group="Center")
    i2 = IntersectionNode(node_id="I2", name="2층 중앙 복도", x=0, y=0, floor=2)
    c1 = ClassroomNode(node_id="C1", name="2학년 3반", x=-20, y=0, floor=2)
    m1 = StoreNode(node_id="M1", name="2층 매점", x=30, y=0, floor=2, base_wait_time=120.0)

    # --- 3층 노드 세팅 ---
    s31= StairsNode(node_id="S31", name='중앙 계단(3F)', x=5, y=5, floor=3, stair_group="Center")
    s32= StairsNode(node_id="S32", name='회전 계단(3F)', x=0, y=-1, floor=3, stair_group="Side")
    i3 = IntersectionNode(node_id="I3", name="3층 중앙 복도", x=0, y=0, floor=3)
    r3 = RestroomNode(node_id="R3", name="3층 화장실", x=-13, y=0, floor=3, base_wait_time=30.0)
    m3 = StoreNode(node_id="M3", name="3층 매점", x=0, y=5, floor=3, base_wait_time=120.0)
    c3 = ClassroomNode(node_id="C3", name="3학년 8반", x=-10, y=0, floor=3)
    h3= HomebaseNode(node_id="H3", name='홈베이스', x=0, y=-12, floor=3)
    
    # --- 4층 노드 세팅 ---
    s41= StairsNode(node_id="S41", name='중앙 계단(4F)', x=5, y=9, floor=4, stair_group="Center")
    s42= StairsNode(node_id="S42", name='회전 계단(4F)', x=0, y=-1, floor=4, stair_group="Side")
    i4 = IntersectionNode(node_id="I4", name="4층 중앙 복도", x=0, y=0, floor=4)
    r41 = RestroomNode(node_id="R41", name="4층 화장실1", x=0, y=9, floor=4, base_wait_time=30.0)
    r42 = RestroomNode(node_id="R42", name="4층 화장실2", x=-13, y=0, floor=4, base_wait_time=30.0)
    

    # 맵에 노드 등록
    for node in [s31, s32, i3, r3, m3, c3, h3 s41,s42,i4,r41,r42]:
        school_map.add_node(node)

    # ==========================================
    # 2. 노드 간 연결 (길/네트워크 형성)
    # ==========================================
    # 1층 연결 (복도 ↔ 화장실, 복도 ↔ 계단)
    school_map.connect_nodes("I1", "R1")
    school_map.connect_nodes("I1", "S1")
    
    # 2층 연결 (계단 ↔ 복도, 복도 ↔ 교실, 복도 ↔ 매점)
    school_map.connect_nodes("S2", "I2")
    school_map.connect_nodes("I2", "C1")
    school_map.connect_nodes("I2", "M1")
    
    #3층 연결
    school_map.connect_nodes("I3", "S31")
    school_map.connect_nodes("I3", "C3")
    school_map.connect_nodes("I3", "M3")
    school_map.connect_nodes("I3", "S32")
    school_map.connect_nodes("C3", "R3")
    school_map.connect_nodes("S32", "H3")
    
    #4층 연결
    school_map.connect_nodes("S41", "R41")
    school_map.connect_nodes("R41", "I4")
    school_map.connect_nodes("I4", "R42")
    school_map.connect_nodes("I4", "S42")

    # 층간 계단 연결 (길찾기 알고리즘이 층계를 타고 넘어가려면 서로 연결되어 있어야 함)
    school_map.connect_nodes("S31", "S41")
    school_map.connect_nodes("S32", "S42")

    # ==========================================
    # 3. 시뮬레이션 환경 세팅
    # ==========================================
    # 10분(600초) 쉬는 시간, 걷는 속도 1.5m/s (빠른 걸음)
    time_mgr = TimeManager("2교시_쉬는시간", max_duration_sec=600, walking_speed_m_s=1.5)

    # [테스트용 혼잡도 함수]
    # 누적된 시간이 1분(60초)을 넘어가면 사람들이 몰려서 소요시간이 1.5배 증가한다고 가정
    def dummy_congestion(base_time, current_time):
        if current_time > 60:
            return base_time * 1.5
        return base_time

    # ==========================================
    # 4. 시나리오 실행 (다익스트라 알고리즘이 아래 리스트를 뽑아줬다고 가정)
    # ==========================================
    # 시나리오: 2학년 3반 학생이 1층 화장실에 가는 경로
    # [교실] -> [2층 복도] -> [2층 계단] -> [1층 계단] -> [1층 복도] -> [화장실]
    sample_path = [c1, i2, s2, s1, i1, r1]

    # 실행
    simulate_student_movement(
        path=sample_path, 
        destination_node=r1, 
        time_manager=time_mgr, 
        congestion_func=dummy_congestion
    )