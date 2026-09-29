"""帮派盟战与沙盘推演系统"""
import math
from dataclasses import dataclass, field

# 据点休整期（秒），默认30分钟
DEFAULT_COOLDOWN_SECONDS = 30 * 60
# 战争迷雾：己方据点的默认视野半径（沙盘坐标单位）
DEFAULT_VISION_RANGE = 100.0
# 基础行军速度（沙盘坐标单位/小时），天气与兵力规模会修正
DEFAULT_MARCH_SPEED = 50.0
# 粮草：每名士兵基础消耗 + 每单位行军距离的额外消耗
FOOD_PER_TROOP = 0.05
FOOD_PER_TROOP_PER_DISTANCE = 0.002
# 士气
MORALE_BASE = 100
MORALE_MAX = 200
MORALE_MIN = 0
MORALE_WIN_GAIN = 10
MORALE_LOSS_DROP = 10
MORALE_STREAK_STEP = 5
# 撤退
DEFAULT_RETREAT_LOSS_RATE = 0.20
RETREAT_MORALE_DROP = 15
# 战功权重
MERIT_PER_KILL = 1
MERIT_PER_CAPTURE = 10
MERIT_PER_DEFEND = 5
MERIT_PER_ASSIST = 2
# 匹配
MAX_LEVEL_DIFF = 5
MAX_POWER_RATIO = 2.0
MAX_WIN_RATE_DIFF = 0.25

# 天气对命中率（按攻击类型）与行军速度的修正
WEATHER_MODIFIERS = {
    "sunny":  {"ranged": 1.0, "melee": 1.0, "speed": 1.0},
    "cloudy": {"ranged": 1.0, "melee": 1.0, "speed": 1.0},
    "rain":   {"ranged": 0.8, "melee": 0.95, "speed": 0.8},
    "snow":   {"ranged": 0.9, "melee": 0.9, "speed": 0.7},
    "fog":    {"ranged": 0.85, "melee": 1.0, "speed": 0.9},
}


@dataclass
class Stronghold:
    sid: str
    name: str
    owner: str = ""
    troops: int = 0
    cooldown_until: float = 0.0
    x: float = 0.0
    y: float = 0.0


class SandtableSystem:
    def __init__(self):
        self.strongholds: dict[str, Stronghold] = {}
        # 战争迷雾默认开启：只能看到己方视野内的敌方单位
        self.fog_of_war: bool = True
        self.vision_range: float = DEFAULT_VISION_RANGE
        # 手动侦察过的据点：guild_id -> {stronghold_id}
        self.scouted: dict[str, set[str]] = {}
        # 据点间行军距离表：("s1", "s2") -> distance
        self.distances: dict[tuple[str, str], float] = {}
        # 据点被占领后的休整期（秒）
        self.cooldown_duration: float = DEFAULT_COOLDOWN_SECONDS
        self.march_speed: float = DEFAULT_MARCH_SPEED
        # 士气与连胜/连败场次
        self.morale: dict[str, float] = {}
        self.morale_streaks: dict[str, int] = {}
        # 天气：sunny / cloudy / rain / snow / fog
        self.weather: str = "sunny"
        # 帮派历史战绩：guild_id -> [wins, losses]
        self.guild_records: dict[str, list[int]] = {}
        # 撤退损失比例
        self.retreat_loss_rate: float = DEFAULT_RETREAT_LOSS_RATE

    # ---------- bug1: 战争迷雾 ----------
    def can_see_enemy(self, guild_id: str, stronghold_id: str) -> bool:
        """迷雾开启时，仅当据点在己方视野范围内（或被侦察过）才可见。"""
        if not self.fog_of_war:
            return True
        target = self.strongholds.get(stronghold_id)
        if target is None:
            return False
        if target.owner == guild_id:
            return True
        if stronghold_id in self.scouted.get(guild_id, set()):
            return True
        for own in self.strongholds.values():
            if own.owner != guild_id:
                continue
            if self._coord_distance(own, target) <= self.vision_range:
                return True
        return False

    def scout(self, guild_id: str, stronghold_id: str) -> None:
        """消耗侦察能力后，可暂时看到迷雾中的某个据点。"""
        self.scouted.setdefault(guild_id, set()).add(stronghold_id)

    @staticmethod
    def _coord_distance(a: Stronghold, b: Stronghold) -> float:
        return math.hypot(a.x - b.x, a.y - b.y)

    # ---------- bug2: 据点休整期 ----------
    def can_attack(self, stronghold_id: str, current_time: float) -> bool:
        """休整期内（cooldown_until 之前）不能再次攻击该据点。"""
        stronghold = self.strongholds.get(stronghold_id)
        if stronghold is None:
            return False
        return current_time >= stronghold.cooldown_until

    def capture_stronghold(self, guild_id: str, stronghold_id: str,
                           current_time: float, troops: int = 0) -> Stronghold:
        """占领据点并进入休整期，期间该据点不能被再次攻击。"""
        stronghold = self.strongholds[stronghold_id]
        stronghold.owner = guild_id
        stronghold.troops = troops
        stronghold.cooldown_until = current_time + self.cooldown_duration
        return stronghold

    # ---------- bug3: 行军时间 ----------
    def get_distance(self, from_sid: str, to_sid: str) -> float:
        if from_sid == to_sid:
            return 0.0
        if (from_sid, to_sid) in self.distances:
            return float(self.distances[(from_sid, to_sid)])
        if (to_sid, from_sid) in self.distances:
            return float(self.distances[(to_sid, from_sid)])
        source = self.strongholds.get(from_sid)
        target = self.strongholds.get(to_sid)
        if source is not None and target is not None:
            return self._coord_distance(source, target)
        return 0.0

    def get_march_time(self, from_sid: str, to_sid: str, troops: int,
                       weather: str | None = None) -> float:
        """按距离计算行军小时数；天气降速、大部队臃肿都会拉长时间。"""
        distance = self.get_distance(from_sid, to_sid)
        if distance <= 0:
            return 0.0
        weather = weather or self.weather
        speed_mod = self.get_weather_speed_modifier(weather)
        # 兵力规模修正：每5万部队速度下降约一半
        troop_mod = 1.0 / (1.0 + max(troops, 0) / 50000.0)
        effective_speed = self.march_speed * speed_mod * troop_mod
        return round(distance / effective_speed, 2)

    def dispatch_troops(self, from_sid: str, to_sid: str, troops: int,
                        current_time: float, weather: str | None = None) -> dict:
        """调兵：返回到达时间与行军耗时（小时）。"""
        hours = self.get_march_time(from_sid, to_sid, troops, weather)
        return {
            "from": from_sid,
            "to": to_sid,
            "troops": troops,
            "march_hours": hours,
            "arrival_time": current_time + hours * 3600,
        }

    # ---------- bug4: 粮草随兵力与距离变化 ----------
    def get_food_consumption(self, troops: int, distance: float) -> float:
        """粮草 = 兵力 * 单兵基础消耗 + 兵力 * 行军距离 * 远距离补给系数。"""
        troops = max(troops, 0)
        distance = max(distance, 0.0)
        consumption = (
            troops * FOOD_PER_TROOP
            + troops * distance * FOOD_PER_TROOP_PER_DISTANCE
        )
        return round(consumption, 2)

    # ---------- bug5: 连胜/连败影响士气 ----------
    def update_morale(self, guild_id: str, win: bool) -> None:
        current = self.morale.get(guild_id, MORALE_BASE)
        streak = self.morale_streaks.get(guild_id, 0)
        if win:
            streak = streak + 1 if streak > 0 else 1
            delta = MORALE_WIN_GAIN + (streak - 1) * MORALE_STREAK_STEP
            current = min(MORALE_MAX, current + delta)
        else:
            streak = streak - 1 if streak < 0 else -1
            delta = MORALE_LOSS_DROP + (abs(streak) - 1) * MORALE_STREAK_STEP
            current = max(MORALE_MIN, current - delta)
        self.morale[guild_id] = current
        self.morale_streaks[guild_id] = streak

    def get_combat_modifier(self, guild_id: str) -> dict:
        """士气动态影响攻防：高士气加攻加防，低士气打折。"""
        morale = self.morale.get(guild_id, MORALE_BASE)
        attack_mod = max(0.5, min(1.5, morale / 100.0))
        defense_mod = max(0.75, min(1.25, 0.75 + morale / 400.0))
        return {
            "morale": morale,
            "streak": self.morale_streaks.get(guild_id, 0),
            "attack_modifier": round(attack_mod, 3),
            "defense_modifier": round(defense_mod, 3),
        }

    # ---------- bug6: 天气影响命中率与行军速度 ----------
    def get_weather_modifier(self, weather: str, attack_type: str) -> float:
        """返回命中率/伤害修正：雨天远程攻击 -20%。"""
        return WEATHER_MODIFIERS.get(weather, WEATHER_MODIFIERS["sunny"]).get(
            attack_type, 1.0
        )

    def get_weather_speed_modifier(self, weather: str) -> float:
        """天气对行军速度的修正（雨雪天移动变慢）。"""
        return WEATHER_MODIFIERS.get(weather, WEATHER_MODIFIERS["sunny"])["speed"]

    # ---------- bug7: 战功综合计算 ----------
    def calculate_battle_merit(self, kills: int, captures: int,
                               defends: int, assists: int) -> int:
        """战功 = 击杀 + 占点*10 + 防守*5 + 助攻*2。"""
        return (
            max(kills, 0) * MERIT_PER_KILL
            + max(captures, 0) * MERIT_PER_CAPTURE
            + max(defends, 0) * MERIT_PER_DEFEND
            + max(assists, 0) * MERIT_PER_ASSIST
        )

    # ---------- bug8: 战力区间 + 历史战绩 + 等级匹配 ----------
    def set_guild_record(self, guild_id: str, wins: int, losses: int) -> None:
        self.guild_records[guild_id] = [max(wins, 0), max(losses, 0)]

    def record_battle_result(self, guild_id: str, win: bool) -> None:
        record = self.guild_records.setdefault(guild_id, [0, 0])
        record[0 if win else 1] += 1

    @staticmethod
    def _win_rate(wins: int, losses: int) -> float | None:
        total = wins + losses
        return wins / total if total > 0 else None

    def match_guilds(self, g1_level: int, g1_power: int,
                     g2_level: int, g2_power: int,
                     g1_id: str | None = None,
                     g2_id: str | None = None) -> bool:
        # 帮派等级差
        if abs(g1_level - g2_level) > MAX_LEVEL_DIFF:
            return False
        # 战力区间：双方战力倍数不得超过阈值
        low = min(g1_power, g2_power)
        high = max(g1_power, g2_power)
        if low <= 0:
            if high > 0:
                return False
        elif high / low > MAX_POWER_RATIO:
            return False
        # 历史战绩：双方都有战绩时，胜率差不能过大
        if g1_id is not None and g2_id is not None:
            r1 = self.guild_records.get(g1_id)
            r2 = self.guild_records.get(g2_id)
            if r1 is not None and r2 is not None:
                w1 = self._win_rate(r1[0], r1[1])
                w2 = self._win_rate(r2[0], r2[1])
                if w1 is not None and w2 is not None:
                    if abs(w1 - w2) > MAX_WIN_RATE_DIFF:
                        return False
        return True

    # ---------- bug9: 撤退惩罚 ----------
    def retreat(self, guild_id: str, troops: int) -> dict:
        """撤退损失默认20%兵力并降低士气，同时中断连胜。"""
        lost_troops = math.ceil(max(troops, 0) * self.retreat_loss_rate)
        current = self.morale.get(guild_id, MORALE_BASE)
        new_morale = max(MORALE_MIN, current - RETREAT_MORALE_DROP)
        self.morale[guild_id] = new_morale
        # 撤退中断连胜，但不叠加败场计数
        if self.morale_streaks.get(guild_id, 0) > 0:
            self.morale_streaks[guild_id] = 0
        return {
            "lost_troops": lost_troops,
            "morale_change": -RETREAT_MORALE_DROP,
            "remaining_troops": max(troops, 0) - lost_troops,
        }
