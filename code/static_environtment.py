from enum import Enum
from typing import Dict, List, Optional

# 노드의 종류를 정의하는 Enum
class NodeCategory(Enum):
    CLASSROOM = "교실"
    FACILITY = "편의시설"   # 매점, 화장실 등 대기가 발생하는 곳
    TRANSITION = "이동통로" # 계단, 엘리베이터 등 층간 이동 수단

# 1. 최상위 기본 노드 클래스
class BaseNode:
    def __init__(self, node_id: str, name: str, floor: int, category: NodeCategory):
        self.node_id = node_id      # 고유 식별자 (예: "R-201", "F-STORE")
        self.name = name            # 화면에 표시할 이름 (예: "2학년 1반", "매점")
        self.floor = floor          # 층수
        self.category = category    # 노드 타입 분류

    def __repr__(self):
        return f"[{self.category.value}] {self.name} ({self.floor}F)"


# 2. 편의시설 노드 (BaseNode 상속)
class FacilityNode(BaseNode):
    def __init__(self, node_id: str, name: str, floor: int, base_wait_time: float, congestion_profile: Dict[str, float]):
        super().__init__(node_id, name, floor, NodeCategory.FACILITY)
        self.base_wait_time = base_wait_time          # 기본 소요 시간 (초)
        self.congestion_profile = congestion_profile  # 시간대별 혼잡도 지연 함수/가중치

    def get_expected_wait_time(self, current_time_slot: str) -> float:
        """
        현재 시간대(예: '1교시_쉬는시간')를 입력받아 
        혼잡도 가중치가 반영된 예상 대기 시간을 반환합니다.
        """
        weight = self.congestion_profile.get(current_time_slot, 1.0)
        return self.base_wait_time * weight


# 3. 이동 통로 노드 (BaseNode 상속)
class TransitionNode(BaseNode):
    def __init__(self, node_id: str, name: str, floor: int, transition_type: str):
        super().__init__(node_id, name, floor, NodeCategory.TRANSITION)
        self.transition_type = transition_type  # "STAIRS"(계단) 또는 "ELEVATOR"(엘리베이터)
        self.is_accessible = True               # 이동 가능 여부 (공사 중 등 예외 처리용)


# 4. 경로(간선) 클래스
class PathEdge:
    def __init__(self, source: BaseNode, target: BaseNode, distance: float, is_stairway: bool = False):
        self.source = source          # 출발 노드 객체
        self.target = target          # 도착 노드 객체
        self.distance = distance      # 물리적 거리 또는 기본 이동 시간(초)
        self.is_stairway = is_stairway # 계단 포함 여부

    def calculate_travel_time(self, walking_speed: float = 1.0) -> float:
        """
        기본 보행 속도를 바탕으로 순수 이동 시간을 계산합니다.
        계단일 경우 이동 효율 저하를 가중치로 보정할 수 있습니다.
        """
        modifier = 1.5 if self.is_stairway else 1.0
        return (self.distance / walking_speed) * modifier


# 5. 학교 전체 지도(그래프) 관리 클래스
class SchoolGraphMap:
    def __init__(self):
        self.nodes: Dict[str, BaseNode] = {}       # {node_id: Node 객체}
        self.edges: Dict[str, List[PathEdge]] = {} # 인접 리스트 구조 {node_id: [연결된 간선들]}

    def add_node(self, node: BaseNode):
        """맵에 새로운 장소(노드)를 추가합니다."""
        self.nodes[node.node_id] = node
        if node.node_id not in self.edges:
            self.edges[node.node_id] = []

    def add_edge(self, source_id: str, target_id: str, distance: float, is_stairway: bool = False):
        """두 장소 사이의 이동 경로(양방향 간선)를 연결합니다."""
        if source_id not in self.nodes or target_id not in self.nodes:
            raise ValueError("출발 또는 도착 노드가 맵에 존재하지 않습니다.")
        
        source_node = self.nodes[source_id]
        target_node = self.nodes[target_id]
        
        # 학교 통로는 보통 양방향 통행이 가능하므로 두 방향 모두 추가
        edge_forward = PathEdge(source_node, target_node, distance, is_stairway)
        edge_backward = PathEdge(target_node, source_node, distance, is_stairway)
        
        self.edges[source_id].append(edge_forward)
        self.edges[target_id].append(edge_backward)

    def get_neighbors(self, node_id: str) -> List[PathEdge]:
        """특정 장소에서 이동할 수 있는 인접 경로 목록을 반환합니다."""
        return self.edges.get(node_id, [])
    
#시간 정의 객체
class TimeManager:
    def __init__(self, time_slot_name: str, max_duration_sec: int = 600):
        """
        :param time_slot_name: 현재 쉬는 시간의 이름 (예: "1교시_쉬는시간")
        :param max_duration_sec: 쉬는 시간의 총 길이 (기본값 600초 = 10분)
        """
        self.current_time_slot = time_slot_name  # 혼잡도 프로필 조회를 위한 시간대 식별자
        self.max_duration_sec = max_duration_sec # 제한 시간 (초)
        self.elapsed_sec = 0.0                   # 현재까지 누적된 소요 시간 (초)

    def add_time(self, seconds: float):
        """이동 또는 대기로 인해 발생한 소요 시간을 누적합니다."""
        if seconds < 0:
            raise ValueError("소요 시간은 음수가 될 수 없습니다.")
        self.elapsed_sec += seconds

    def get_remaining_time(self) -> float:
        """남은 쉬는 시간을 초 단위로 반환합니다."""
        return max(0.0, self.max_duration_sec - self.elapsed_sec)

    def is_time_over(self) -> bool:
        """제한 시간(10분)을 초과했는지 확인합니다."""
        return self.elapsed_sec > self.max_duration_sec

    def reset(self):
        """새로운 경로 탐색을 위해 누적 시간을 0으로 초기화합니다."""
        self.elapsed_sec = 0.0
        
    def __repr__(self):
        minutes = int(self.elapsed_sec // 60)
        seconds = int(self.elapsed_sec % 60)
        return f"[{self.current_time_slot}] 누적 소요 시간: {minutes}분 {seconds}초 / 남은 시간: {int(self.get_remaining_time())}초"