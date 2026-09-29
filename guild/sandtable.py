"""帮派盟战与沙盘推演系统 - 含9个bug"""
from dataclasses import dataclass, field

@dataclass
class Stronghold:
    sid: str
    name: str
    owner: str = ""
    troops: int = 0
    cooldown_until: float = 0  # bug2: 无休整

class SandtableSystem:
    def __init__(self):
        self.strongholds: dict[str, Stronghold] = {}
        self.fog_of_war: bool = False  # bug1: 无迷雾
        self.march_time: dict[str, float] = {}  # bug3: 无行军时间
        self.morale: dict[str, float] = {}  # bug5: 只看胜负
        self.weather: str = "sunny"  # bug6: 无天气影响

    def can_see_enemy(self, guild_id: str, stronghold_id: str) -> bool:
        # bug1: 全图可见
        return True

    def can_attack(self, stronghold_id: str, current_time: float) -> bool:
        # bug2: 无休整期
        return True

    def get_march_time(self, from_sid: str, to_sid: str, troops: int) -> float:
        # bug3: 瞬移
        return 0.0

    def get_food_consumption(self, troops: int, distance: float) -> float:
        # bug4: 固定消耗
        return 10.0

    def update_morale(self, guild_id: str, win: bool):
        # bug5: 只看胜负
        self.morale[guild_id] = 100 if win else 50

    def get_weather_modifier(self, weather: str, attack_type: str) -> float:
        # bug6: 无天气影响
        return 1.0

    def calculate_battle_merit(self, kills: int, captures: int, defends: int, assists: int) -> int:
        # bug7: 只看击杀
        return kills

    def match_guilds(self, g1_level: int, g1_power: int, g2_level: int, g2_power: int) -> bool:
        # bug8: 只看等级
        return abs(g1_level - g2_level) <= 5

    def retreat(self, guild_id: str, troops: int) -> dict:
        # bug9: 撤退无惩罚
        return {"lost_troops": 0, "morale_change": 0}
