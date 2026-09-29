"""帮派盟战与沙盘推演系统 - 红态测试"""
import pytest, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from guild.sandtable import SandtableSystem, Stronghold

class TestFogOfWar:
    def test_enemy_not_visible_without_scout(self):
        st = SandtableSystem()
        st.fog_of_war = True
        st.strongholds["s1"] = Stronghold("s1", "castle", owner="enemy")
        assert st.can_see_enemy("my_guild", "s1") == False

class TestCooldown:
    def test_cannot_attack_during_cooldown(self):
        st = SandtableSystem()
        st.strongholds["s1"] = Stronghold("s1", "castle", cooldown_until=100.0)
        assert st.can_attack("s1", 50.0) == False
        assert st.can_attack("s1", 150.0) == True

class TestMarchTime:
    def test_longer_distance_takes_more_time(self):
        st = SandtableSystem()
        t1 = st.get_march_time("s1", "s2", 100)
        # 应该有距离概念
        assert hasattr(st, "distances")
        st.distances = {("s1","s2"): 10, ("s1","s3"): 100}
        t_short = st.get_march_time("s1", "s2", 100)
        t_long = st.get_march_time("s1", "s3", 100)
        assert t_long > t_short

class TestFoodConsumption:
    def test_more_troops_consume_more_food(self):
        st = SandtableSystem()
        c1 = st.get_food_consumption(100, 10)
        c2 = st.get_food_consumption(10000, 10)
        assert c2 > c1

class TestMoraleStreak:
    def test_win_streak_increases_morale(self):
        st = SandtableSystem()
        st.morale["g1"] = 100
        st.update_morale("g1", True)
        st.update_morale("g1", True)
        assert st.morale["g1"] > 100

class TestWeatherEffect:
    def test_rain_reduces_ranged_attack(self):
        st = SandtableSystem()
        m1 = st.get_weather_modifier("sunny", "ranged")
        m2 = st.get_weather_modifier("rain", "ranged")
        assert m2 < m1

class TestBattleMerit:
    def test_capture_and_defense_count(self):
        st = SandtableSystem()
        m1 = st.calculate_battle_merit(kills=10, captures=0, defends=0, assists=0)
        m2 = st.calculate_battle_merit(kills=0, captures=5, defends=5, assists=0)
        assert m2 > 0

class TestGuildMatching:
    def test_matching_considers_power(self):
        st = SandtableSystem()
        # 等级相同但战力差距大不应匹配
        assert st.match_guilds(10, 1000, 10, 100000) == False

class TestRetreatPenalty:
    def test_retreat_loses_troops(self):
        st = SandtableSystem()
        result = st.retreat("g1", 1000)
        assert result["lost_troops"] > 0
