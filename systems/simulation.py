# systems/simulation.py

def simulate_population(nation):
    """Calculates population growth."""
    pgr_base = 0.010  
    hf = getattr(nation, 'healthcare_factor', 1.0)
    ef = getattr(nation, 'education_factor', 1.0)
    fsf = getattr(nation, 'food_security_factor', 1.0)
    qlf = getattr(nation, 'quality_of_life_factor', 1.0)
    pm_pop = getattr(nation, 'policy_multiplier_pop', 1.0)
    
    growth_rate = pgr_base * hf * ef * fsf * qlf * pm_pop
    new_population = int(nation.population * (1 + growth_rate))
    growth_amount = new_population - nation.population
    
    nation.population = new_population
    return growth_amount

def simulate_economy(nation):
    """Calculates GDP growth, taxes, interest, and deficit handling."""
    # 1. Base growth from your dynamic economic rate (e.g., 2.5% = 0.025)
    base_growth = nation.economic_growth_rate / 100.0
    stability_mod = (nation.political_stability - 50) / 1000.0
    
    # 2. Defaulting Penalty: If debt is over 40%, the economy crashes (-2% growth)
    if nation.debt_to_gdp_ratio > 40:
        base_growth -= 0.02 
        
    growth_rate = base_growth + stability_mod
    growth_amount = nation.gdp * growth_rate
    nation.gdp += growth_amount
    
    # 3. Revenue & Expenses
    tax_revenue = nation.gdp * 0.15 
    interest_payment = nation.debt * 0.05 # 5% interest on current debt
    
    nation.treasury += (tax_revenue - interest_payment)

    # 4. Emergency Deficit Bailout
    deficit = 0.0
    if nation.treasury < 0:
        deficit = abs(nation.treasury)
        nation.debt += deficit # Force borrowing to cover the deficit
        nation.treasury = 0.0

    return growth_amount, tax_revenue, interest_payment, deficit