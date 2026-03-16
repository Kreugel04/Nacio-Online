# models/nation.py
import random

class Nation:
    def __init__(self, name: str, year: int, population: int, gdp: float, military_strength: float, political_stability: float, briefing: str = "", save_name: str = "default", treasury: float = None, world_gdp: dict = None, world_military: dict = None, stat_history: list = None, flag_emoji: str = "🏳️", industrialization_level: int = 1, tech_level: int = 1, nation_era: str = "Stone Age", regional_neighbors: dict = None, debt: float = 0.0, economic_growth_rate: float = 2.0):
        self.name = name
        self.save_name = save_name
        self.starting_year = year 
        self.briefing_text = briefing
        self.flag_emoji = flag_emoji

        self.industrialization_level = industrialization_level
        self.tech_level = tech_level
        self.nation_era = nation_era
            
        self.population = population
        self.public_approval = 50.0  
        self.gdp = gdp    
        self.treasury = treasury if treasury is not None else (gdp * 0.20)   
        self.military_strength = military_strength
        self.political_stability = political_stability
        
        # --- NEW FINANCE ATTRIBUTES ---
        self.debt = debt
        self.economic_growth_rate = economic_growth_rate
        self.intelligence_power = 0.0
        
        self.world_gdp = world_gdp if world_gdp is not None else {}
        self.world_military = world_military if world_military is not None else {}
        self.regional_neighbors = regional_neighbors if regional_neighbors is not None else {}
        self.stat_history = stat_history if stat_history is not None else []
        self.history = [] 

        self.active_laws = []
        self.active_treaties = [] # NEW: Stores treaties
        self.diplomatic_chats = {}

    @property
    def gdp_per_capita(self):
        if self.population <= 0: return 0
        return (self.gdp * 1_000_000_000) / self.population

    @property
    def debt_to_gdp_ratio(self):
        """Calculates debt as a percentage of GDP."""
        if self.gdp <= 0: return 0
        return (self.debt / self.gdp) * 100.0

    @property
    def debt_tier(self):
        """Classifies the economic health based on debt ratio."""
        ratio = self.debt_to_gdp_ratio
        if ratio <= 10: return "Healthy"
        elif ratio <= 20: return "Acceptable"
        elif ratio <= 30: return "Strained"
        elif ratio <= 40: return "Critical"
        else: return "DEFAULTING"

    @property
    def combat_power(self):
        tech_modifier = 1 + (self.tech_level * 0.20)
        ind_modifier = 1 + (self.industrialization_level * 0.20)
        stability_modifier = max(0.1, self.political_stability / 100.0) 
        return self.military_strength * tech_modifier * ind_modifier * stability_modifier

    @property
    def state_power_index(self):
        """Calculates the normalized 'State Rank/Capacity' from 1 to 100."""
        # 1. Base is driven by public sentiment and control
        base_score = (self.political_stability + self.public_approval) / 2.0
        
        # 2. Debt Modifiers (Rewards good economy, punishes defaulting)
        debt_ratio = self.debt_to_gdp_ratio
        if debt_ratio < 15: debt_mod = 10
        elif debt_ratio > 40: debt_mod = -20
        else: debt_mod = 0
            
        # 3. Development Modifiers
        dev_mod = (self.tech_level + self.industrialization_level) * 1.5
        
        # Calculate final index, clamped between 1 and 100
        final_index = base_score + debt_mod + dev_mod
        return max(1.0, min(100.0, final_index))

    def update_era(self):
        gdp_pc = self.gdp_per_capita
        if self.tech_level >= 5 and self.industrialization_level >= 5 and gdp_pc > 30000:
            self.nation_era = "Space Age"
        elif self.tech_level >= 5 and self.industrialization_level >= 4:
            self.nation_era = "Cyber Age"
        elif self.tech_level >= 4 and self.industrialization_level >= 3:
            self.nation_era = "Industrialization Age"
        elif self.tech_level >= 3 and self.industrialization_level >= 2:
            self.nation_era = "Steel Age"
        elif self.tech_level >= 2 and self.industrialization_level >= 2 and self.political_stability >= 40:
            self.nation_era = "Iron Age"
        elif self.tech_level >= 1 and gdp_pc > 500:
            self.nation_era = "Mythic Age"
        elif self.industrialization_level >= 2:
            self.nation_era = "Bronze Age"
        else:
            self.nation_era = "Stone Age"

    def execute_war(self, target_name, target_base_strength, force_commitment_pct):
        player_committed_power = self.combat_power * (force_commitment_pct / 100.0)
        enemy_tech_mod = 1 + (random.randint(max(1, int(self.tech_level)-1), min(5, int(self.tech_level)+1)) * 0.20)
        enemy_combat_power = target_base_strength * enemy_tech_mod
        
        player_roll = player_committed_power * random.uniform(0.85, 1.15)
        enemy_roll = enemy_combat_power * random.uniform(0.85, 1.15)
        
        war_cost_gdp = self.gdp * (force_commitment_pct / 200.0) 
        self.treasury -= war_cost_gdp
        
        if player_roll > enemy_roll:
            result = "VICTORY"
            self.gdp += target_base_strength * 0.5
            self.population += int(target_base_strength * 10000)
            self.military_strength -= (self.military_strength * 0.05) 
            self.political_stability += 5.0
            self.public_approval += 10.0
        else:
            result = "DEFEAT"
            self.military_strength -= (self.military_strength * (force_commitment_pct / 100.0) * 0.5) 
            self.political_stability -= 15.0
            self.public_approval -= 20.0
            
        return {
            "result": result,
            "player_power": int(player_roll),
            "enemy_power": int(enemy_roll),
            "cost_billions": war_cost_gdp
        }

    def process_turn(self):
        self.update_era()
    
    def add_law(self, year, title, description, effects):
        self.active_laws.append({
            "year": year,
            "title": title,
            "description": description,
            "effect": effects # We keep the key as 'effect' so old saves don't break!
        })
    
    def add_treaty(self, year, target_nation, title, duration, description, effects):
        self.active_treaties.append({
            "year": year,
            "target": target_nation,
            "title": title,
            "duration": duration,
            "description": description,
            "effect": effects
        })

    def record_stats(self, year):
        self.stat_history.append({
            "Year": year,
            "Population": self.population,
            "GDP ($B)": self.gdp,
            "Treasury ($B)": self.treasury,
            "Debt ($B)": self.debt,
            "Stability (%)": self.political_stability,
            "Approval (%)": self.public_approval
        })

    def add_event(self, year, summary, law_impact="None", event="None"):
        self.history.append({"year": year, "summary": summary, "law_impact": law_impact, "event": event})

    def to_dict(self):
        return {
            "name": self.name,
            "save_name": self.save_name,
            "starting_year": self.starting_year,
            "briefing_text": self.briefing_text,
            "flag_emoji": self.flag_emoji,
            "industrialization_level": self.industrialization_level,
            "tech_level": self.tech_level,
            "nation_era": self.nation_era,
            "population": self.population,
            "public_approval": self.public_approval,
            "gdp": self.gdp,
            "treasury": self.treasury,
            "debt": self.debt,
            "economic_growth_rate": self.economic_growth_rate,
            "world_gdp": self.world_gdp,
            "world_military": self.world_military,
            "regional_neighbors": self.regional_neighbors,
            "stat_history": self.stat_history,
            "military_strength": self.military_strength,
            "political_stability": self.political_stability,
            "history": self.history,
            "active_laws": self.active_laws,
            "intelligence_power": self.intelligence_power,
            "active_treaties": self.active_treaties,
            "diplomatic_chats": self.diplomatic_chats
        }

    @classmethod
    def from_dict(cls, data):
        nation = cls(
            name=data["name"],
            save_name=data.get("save_name", "default"),
            year=data.get("starting_year", 1),
            flag_emoji=data.get("flag_emoji", "🏳️"),
            industrialization_level=data.get("industrialization_level", 1),
            tech_level=data.get("tech_level", 1),
            nation_era=data.get("nation_era", "Stone Age"),
            population=data["population"],
            gdp=data["gdp"],
            treasury=data.get("treasury", data["gdp"] * 0.20), 
            debt=data.get("debt", 0.0),
            economic_growth_rate=data.get("economic_growth_rate", 2.0),
            world_gdp=data.get("world_gdp", {}),
            stat_history=data.get("stat_history", []), 
            world_military=data.get("world_military", {}),
            regional_neighbors=data.get("regional_neighbors", {}),
            military_strength=data["military_strength"],
            political_stability=data["political_stability"],
            briefing=data.get("briefing_text", "")
        )
        nation.public_approval = data.get("public_approval", 50.0)
        nation.history = data.get("history", [])
        nation.active_laws = data.get("active_laws", [])
        nation.intelligence_power = data.get("intelligence_power", 0.0)
        nation.active_treaties = data.get("active_treaties", [])
        nation.diplomatic_chats = data.get("diplomatic_chats", {})
        return nation