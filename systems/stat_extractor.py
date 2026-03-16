# systems/stat_extractor.py
import re

def apply_ai_stats(nation, ai_report):
    """
    Parses the AI report, extracts statistical and factional changes, and applies them.
    """
    if not ai_report or not isinstance(ai_report, str) or "Statistic" not in ai_report:
        print("[SYSTEM LOG]: Extraction aborted - No valid stats section found.")
        return

    print("\n[SYSTEM LOG]: Extracting statistical data from AI report...")
    
    # --- 1. CORE STATS EXTRACTION ---
    try:
        stats_section = ai_report
        if "**Statistical Impact:**" in ai_report:
            stats_section = ai_report.split("**Statistical Impact:**")[-1]
        elif "Statistical Impact:" in ai_report:
            stats_section = ai_report.split("Statistical Impact:")[-1]
        elif "Statistical Updates:" in ai_report:
            stats_section = ai_report.split("Statistical Updates:")[-1]
            
        stats_section = stats_section.split("Factional Reactions:")[0]
        
        # --- THE FIX: Strip brackets and markdown so the regex never fails! ---
        clean_stats = stats_section.replace('[', '').replace(']', '').replace('*', '')
        
        # Regex looks for the Stat Name and grabs the number
        pattern = r'([A-Za-z\s]+):\s*([+-]?\d+(?:\.\d+)?)(%?)'
        matches = re.findall(pattern, clean_stats)
        
        if matches:
            for stat_name, value_str, is_percentage in matches:
                stat_name = stat_name.strip().lower()
                value = float(value_str)
                
                if "gdp" in stat_name:
                    change = nation.gdp * (value / 100) if is_percentage else value
                    nation.gdp += change
                
                elif "population" in stat_name:
                    change = int(nation.population * (value / 100)) if is_percentage else int(value)
                    nation.population += change
                        
                elif "military" in stat_name:
                    change = nation.military_strength * (value / 100) if is_percentage else value
                    nation.military_strength += change
                    
                elif "stability" in stat_name:
                    nation.political_stability = max(0.0, min(100.0, nation.political_stability + value))
                    
                elif "approval" in stat_name:
                    nation.public_approval = max(0.0, min(100.0, nation.public_approval + value))
                
                elif "tech" in stat_name:
                    nation.tech_level = max(1.0, min(5.0, nation.tech_level + value))
                    
                elif "ind level" in stat_name or "industrialization" in stat_name:
                    nation.industrialization_level = max(1.0, min(5.0, nation.industrialization_level + value))
                
                elif "intelligence" in stat_name or "intel" in stat_name:
                    nation.intelligence_power = max(0.0, nation.intelligence_power + value)

                elif "economic growth" in stat_name:
                    nation.economic_growth_rate += value
                elif "debt" in stat_name:
                    nation.debt = max(0.0, nation.debt + value) 

        else:
            print("[SYSTEM LOG]: No valid core stat changes found.")
            
    except Exception as e:
        print(f"[SYSTEM LOG]: Core extraction failed: {str(e)}")

    # --- 2. FACTIONAL SUPPORT EXTRACTION ---
    if "Factional Reactions:" in ai_report:
        print("\n[SYSTEM LOG]: Extracting factional shifts...")
        try:
            factions_section = ai_report.split("Factional Reactions:")[1]
            if "Global Reactions Simulated:" in factions_section:
                factions_section = factions_section.split("Global Reactions Simulated:")[0]
                
            faction_pattern = r'([A-Za-z\s]+):.*?\(\s*Support Change:\s*([+-]?\d+(?:\.\d+)?)\s*\)'
            faction_matches = re.findall(faction_pattern, factions_section)
            
            if faction_matches:
                for faction_name, value_str in faction_matches:
                    faction_name = faction_name.strip()
                    value = float(value_str)
                    
                    if not hasattr(nation, 'factions'):
                        nation.factions = {}
                    if faction_name not in nation.factions:
                        nation.factions[faction_name] = 50.0
                        
                    nation.factions[faction_name] += value
                    nation.factions[faction_name] = max(0.0, min(100.0, nation.factions[faction_name]))
                    
        except Exception as e:
            print(f"[SYSTEM LOG]: Faction extraction failed: {str(e)}")