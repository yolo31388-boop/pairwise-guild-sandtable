"""帮派盟战与沙盘推演系统"""
from dataclasses import dataclass, field

# 据点占领后的休整期（秒），默认30分钟
OCCUPY_COOLDOWN = 30 * 60
# 行军速度（距离单位/小时）
MARCH_SPEED = 20.0
# 默认视野范围（距离单位）
VISION_RANGE = 50.0
# 撤退兵力损失比例
RETREAT_LOSS_RATIO = 0.2
# 士气上下限
MORALE_MIN, MORALE_MAX = 0.0, 200.0


@dataclass
class Stronghold:
    sid: str
    name: str
    owner: str = ""
    troops: int = 0
    cooldown_until: float = 0


class SandtableSystem:
    def __init__(self):
        self.strongholds: dict[str, Stronghold] = {}
        self.fog_of_war: bool = False
        self.distances: dict[tuple[str, str], float] = {}
        self.morale: dict[str, float] = {}
        self.streaks: dict[str, int] = {}  # 正数连胜，负数连败
        self.weather: str = "sunny"
        self.vision_range: float = VISION_RANGE

    def _distance(self, from_sid: str, to_sid: str) -> float:
        if (from_sid, to_sid) in self.distances:
            return self.distances[(from_sid, to_sid)]
        if (to_sid, from_sid) in self.distances:
            return self.distances[(to_sid, from_sid)]
        return 50.0  # 未知距离取默认值

    # bug1: 战争迷雾——只能看到己方据点视野范围内的敌方单位
    def can_see_enemy(self, guild_id: str, stronghold_id: str) -> bool:
        if not self.fog_of_war:
            return True
        target = self.strongholds.get(stronghold_id)
        if target is None:
            return False
        if target.owner == guild_id:
            return True
        for sh in self.strongholds.values():
            if sh.owner == guild_id and self._distance(sh.sid, stronghold_id) <= self.vision_range:
                return True
        return False

    # bug2: 占领后休整期内不能再次攻击
    def can_attack(self, stronghold_id: str, current_time: float) -> bool:
        sh = self.strongholds.get(stronghold_id)
        if sh is None:
            return False
        return current_time >= sh.cooldown_until

    def occupy(self, stronghold_id: str, guild_id: str, current_time: float):
        sh = self.strongholds[stronghold_id]
        sh.owner = guild_id
        sh.cooldown_until = current_time + OCCUPY_COOLDOWN

    # bug3: 按距离计算行军时间（秒），雨天减速
    def get_march_time(self, from_sid: str, to_sid: str, troops: int) -> float:
        distance = self._distance(from_sid, to_sid)
        speed = MARCH_SPEED * self.get_weather_modifier(self.weather, "march")
        return distance / speed * 3600.0

    # bug4: 粮草按兵力数量和行军距离计算
    def get_food_consumption(self, troops: int, distance: float) -> float:
        return troops * (1.0 + distance * 0.1)

    # bug5: 连胜/连败动态影响士气
    def update_morale(self, guild_id: str, win: bool):
        streak = self.streaks.get(guild_id, 0)
        streak = streak + 1 if win else streak - 1
        self.streaks[guild_id] = streak
        current = self.morale.get(guild_id, 100.0)
        # 连胜加成递增，连败衰减递增
        delta = 5.0 * abs(streak) if win else -5.0 * abs(streak)
        self.morale[guild_id] = max(MORALE_MIN, min(MORALE_MAX, current + delta))

    def get_combat_modifier(self, guild_id: str) -> float:
        """士气影响攻防属性：100为基准，每点士气±0.5%"""
        return 1.0 + (self.morale.get(guild_id, 100.0) - 100.0) * 0.005

    # bug6: 天气影响命中率和移动速度
    def get_weather_modifier(self, weather: str, attack_type: str) -> float:
        modifiers = {
            "sunny": {"ranged": 1.0, "melee": 1.0, "march": 1.0},
            "rain": {"ranged": 0.8, "melee": 1.0, "march": 0.7},
            "snow": {"ranged": 0.9, "melee": 0.9, "march": 0.5},
            "fog": {"ranged": 0.85, "melee": 1.0, "march": 0.8},
        }
        return modifiers.get(weather, modifiers["sunny"]).get(attack_type, 1.0)

    # bug7: 战功按击杀+占点+防守+助攻综合计算
    def calculate_battle_merit(self, kills: int, captures: int, defends: int, assists: int) -> int:
        return kills * 1 + captures * 20 + defends * 15 + assists * 3

    # bug8: 匹配按帮派等级+战力区间+历史战绩
    def match_guilds(self, g1_level: int, g1_power: int, g2_level: int, g2_power: int,
                     g1_win_rate: float = 0.5, g2_win_rate: float = 0.5) -> bool:
        if abs(g1_level - g2_level) > 5:
            return False
        low, high = min(g1_power, g2_power), max(g1_power, g2_power)
        if high > low * 2:  # 战力差距超过2倍不匹配
            return False
        if abs(g1_win_rate - g2_win_rate) > 0.3:  # 历史战绩差距过大不匹配
            return False
        return True

    # bug9: 撤退损失20%兵力且士气下降
    def retreat(self, guild_id: str, troops: int) -> dict:
        lost = int(troops * RETREAT_LOSS_RATIO)
        before = self.morale.get(guild_id, 100.0)
        self.streaks[guild_id] = 0  # 撤退中断连胜
        self.morale[guild_id] = max(MORALE_MIN, before - 10.0)
        return {
            "lost_troops": lost,
            "remaining_troops": troops - lost,
            "morale_change": self.morale[guild_id] - before,
        }
