# app.py
import streamlit as st
import time
from datetime import datetime
from models.nation import Nation
from core.ai_handler import AIHandler
from systems.stat_extractor import apply_ai_stats
from systems.events import trigger_historical_event
import json
import os
import pandas as pd
from systems.simulation import simulate_economy, simulate_population

# --- HELPER FUNCTIONS ---
def save_game(nation, turn, messages):
    """Saves the current nation state and chat history to a JSON file."""
    if not os.path.exists("saves"):
        os.makedirs("saves")
    
    filename = f"saves/{nation.save_name}.json"
    save_data = {
        "turn_number": turn,
        "nation": nation.to_dict(),
        "messages": messages 
    }
    with open(filename, "w") as f:
        json.dump(save_data, f, indent=4)
    return filename

# --- PAGE CONFIG ---
st.set_page_config(page_title="Nacio: A Global Symphony", layout="wide")

# --- CUSTOM CSS FOR STICKY HEADER ---
st.markdown("""
    <style>
        .main .block-container,
        div[data-testid="stVerticalBlock"],
        div[data-testid="stVerticalBlockBorderWrapper"],
        div[data-testid="stElementContainer"],
        div[data-testid="stTabs"],
        div[data-baseweb="tabs"] { 
            overflow: visible !important;
            clip-path: none !important;
        }

        .main div[data-testid="stElementContainer"]:has(h1) {
            position: sticky !important;
            top: 2.875rem !important; 
            z-index: 1000 !important;
            background-color: #0E1117 !important;
            padding-bottom: 0.5rem !important;
        }
        
        .main div[role="tablist"] {
            position: sticky !important;
            top: 7.2rem !important; 
            z-index: 999 !important;
            background-color: #0E1117 !important;
            padding-top: 10px !important;
            padding-bottom: 10px !important;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1) !important;
        }
        
        div[data-testid="stChatInput"] {
            z-index: 1001 !important;
        }
    </style>
""", unsafe_allow_html=True)

# --- INITIALIZE SESSION STATE & ANTI-REFRESH LOGIC ---
if 'nation' not in st.session_state:
    st.session_state.nation = None
if 'turn' not in st.session_state:
    st.session_state.turn = 1
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'ai' not in st.session_state:
    st.session_state.ai = AIHandler(use_local=False) # <--- Set this to False!
if 'diplomacy_chat' not in st.session_state:
    st.session_state.diplomacy_chat = []
# THE FIX: Initialize the navigation view state!
if 'nav_view' not in st.session_state: 
    st.session_state.nav_view = "💬 Command Center"
if 'jump_to_command' not in st.session_state:
    st.session_state.jump_to_command = False

# --- THE JUMP CATCHER ---
# We change the nav_view BEFORE the sidebar is drawn!
if st.session_state.jump_to_command:
    st.session_state.nav_view = "💬 Command Center"
    st.session_state.jump_to_command = False

# --- ANTI-REFRESH RECOVERY ---
if st.session_state.nation is None and "session" in st.query_params:
    session_name = st.query_params["session"]
    save_file = f"saves/{session_name}.json"
    if os.path.exists(save_file):
        with open(save_file, "r") as f:
            data = json.load(f)
        st.session_state.nation = Nation.from_dict(data["nation"])
        st.session_state.turn = data["turn_number"]
        st.session_state.messages = data.get("messages", [])
        st.session_state.nation.update_era()

# --- BACKWARD COMPATIBILITY PATCH FOR OLD SAVES ---
if st.session_state.nation is not None:
    if not hasattr(st.session_state.nation, 'diplomatic_chats'):
        st.session_state.nation.diplomatic_chats = {}
    if not hasattr(st.session_state.nation, 'active_treaties'):
        st.session_state.nation.active_treaties = []
    if not hasattr(st.session_state.nation, 'intelligence_power'):
        st.session_state.nation.intelligence_power = 0.0

# --- MAIN INTERFACE ---
# 1. MAIN MENU (NO NATION LOADED)
if st.session_state.nation is None:
    st.markdown("<h1 style='text-align: center;'>Nacio: A Global Symphony</h1>", unsafe_allow_html=True)
    st.markdown("<h4 style='text-align: center; color: #888888; margin-bottom: 40px;'>Welcome, Supreme Leader. Select your era.</h4>", unsafe_allow_html=True)
    
    col_new, col_divider, col_load = st.columns([0.45, 0.1, 0.45])
    
    with col_new:
        st.subheader("✨ Forge a New Timeline")
        st.markdown("Enter the annals of history and guide your civilization.")
        country_input = st.text_input("Nation Name", value="Japan")
        year_input = st.number_input("Starting Year", value=1980, step=1)
        
        if st.button("Initialize Simulation", type="primary", use_container_width=True):
            with st.spinner("Establishing chronological uplink..."):
                data = st.session_state.ai.generate_starting_nation(country_input, year_input)
                
                if isinstance(data, dict):
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S") # e.g., 20260316_090619
                    save_name = f"{country_input}_{year_input}_{timestamp}".replace(" ", "_")
                    
                    st.session_state.nation = Nation(
                        name=country_input, year=year_input, 
                        flag_emoji=data.get('flag_emoji', '🏳️'), 
                        population=data['population'], gdp=data['gdp'],
                        military_strength=data['military_strength'], 
                        political_stability=data['political_stability'],
                        industrialization_level=data.get('industrialization_level', 1), 
                        tech_level=data.get('tech_level', 1),
                        regional_neighbors=data.get('regional_neighbors', {}),
                        world_gdp=data.get('world_gdp', {}),
                        world_military=data.get('world_military', {}),
                        briefing=data['briefing'],
                        save_name=save_name,
                        debt=data.get('debt', 0.0), 
                        economic_growth_rate=data.get('economic_growth_rate', 2.5)
                    )
                    st.session_state.turn = int(year_input)
                    st.session_state.nation.update_era() 
                    st.session_state.nation.record_stats(st.session_state.turn)
                    st.session_state.messages = [{"role": "assistant", "content": f"**INITIAL CABINET REPORT:**\n\n{data['briefing']}"}]
                    
                    st.query_params["session"] = save_name
                    save_game(st.session_state.nation, st.session_state.turn, st.session_state.messages)
                    st.rerun()
                elif isinstance(data, str):
                    st.error(f"📡 **COMMUNICATIONS FAILURE:** {data}")
                else:
                    st.error("📡 **COMMUNICATIONS FAILURE:** The AI failed to generate a valid nation state.")

    with col_load:
        st.subheader("📂 Access Data Archives")
        st.markdown("Resume command of an existing timeline.")
        if not os.path.exists("saves"):
            st.info("No archives found. Start a new timeline to save your progress.")
        else:
            save_files = [f for f in os.listdir("saves") if f.endswith('.json')]
            if not save_files:
                st.info("Archive directory is empty.")
            else:
                for file in save_files:
                    c1, c2, c3 = st.columns([0.6, 0.2, 0.2])
                    with c1: 
                        st.caption(file.replace(".json", ""))
                    with c2:
                        if st.button("📂", key=f"load_{file}", help="Load timeline"):
                            with open(f"saves/{file}", "r") as f:
                                data = json.load(f)
                            st.session_state.nation = Nation.from_dict(data["nation"])
                            st.session_state.turn = data["turn_number"]
                            st.session_state.messages = data.get("messages", [])
                            st.session_state.nation.update_era()
                            
                            st.query_params["session"] = file.replace(".json", "")
                            st.rerun()
                    with c3:
                        if st.button("🗑️", key=f"del_{file}", help="Delete timeline"):
                            os.remove(f"saves/{file}")
                            st.toast(f"Deleted {file}")
                            st.rerun()

# 2. MAIN INTERFACE (GAME ACTIVE)
else:
    # --- THE CABINET OFFICE SIDEBAR ---
    with st.sidebar:
        st.title("🏛️ Cabinet Office")
        n = st.session_state.nation
        
        hex_code = "-".join(f"{ord(c):x}" for c in n.flag_emoji)
        twemoji_url = f"https://cdnjs.cloudflare.com/ajax/libs/twemoji/14.0.2/72x72/{hex_code}.png"
        
        st.markdown(f"""
            <div style="text-align: center; margin-bottom: 20px;">
                <img src="{twemoji_url}" style="height: 7rem; filter: drop-shadow(0px 6px 8px rgba(0,0,0,0.4));" alt="{n.flag_emoji}">
            </div>
        """, unsafe_allow_html=True)
        
        st.metric("Nation", n.name)
        st.metric("Year", st.session_state.turn)
        
        st.markdown(f"### 🏛️ Era: {n.nation_era}")
        st.divider()
        
        st.subheader("Core Statistics")
        st.write(f"👥 **Population:** {n.population:,}")
        st.write(f"💰 **GDP:** ${n.gdp:,.2f}B (📈 {n.economic_growth_rate:.1f}%)")
        st.write(f"💵 **GDP Per Capita:** ${n.gdp_per_capita:,.0f}")
        st.write(f"🏦 **Treasury:** ${n.treasury:,.2f}B")
        tier_color = "red" if n.debt_to_gdp_ratio > 40 else "orange" if n.debt_to_gdp_ratio > 20 else "green"
        st.write(f"💳 **National Debt:** ${n.debt:,.2f}B")
        st.markdown(f"**Debt Ratio:** <span style='color:{tier_color}'>{n.debt_to_gdp_ratio:.1f}% ({n.debt_tier})</span>", unsafe_allow_html=True)
        
        st.divider()
        st.subheader("Development Levels")
        st.progress(n.tech_level / 5.0, text=f"🔬 Tech Level: {n.tech_level} / 5")
        st.progress(n.industrialization_level / 5.0, text=f"🏭 Ind. Level: {n.industrialization_level} / 5")
        st.divider()
        
        st.progress(n.political_stability / 100, text=f"⚖️ Stability: {n.political_stability}%")
        st.progress(n.public_approval / 100, text=f"📢 Approval: {n.public_approval}%")

        # --- SIDEBAR NAVIGATION ROUTER ---
        st.divider()
        st.markdown("### 🗺️ Navigation")
        current_view = st.radio("Select View:", 
                                ["💬 Command Center", "📊 National Analytics", "🌍 Foreign Affairs"], 
                                key="nav_view", 
                                label_visibility="collapsed")
        
        st.divider()
        st.subheader("🌍 Global Rankings")
        
        live_gdp_rankings = n.world_gdp.copy()
        live_gdp_rankings[n.name] = n.gdp
        
        live_military_rankings = n.world_military.copy()
        live_military_rankings[n.name] = n.military_strength
        
        sorted_gdp = sorted(live_gdp_rankings.items(), key=lambda x: x[1], reverse=True)
        sorted_mil = sorted(live_military_rankings.items(), key=lambda x: x[1], reverse=True)
        
        rank_tab1, rank_tab2 = st.tabs(["💰 Top Economies", "⚔️ Top Militaries"])
        
        with rank_tab1:
            df_gdp = pd.DataFrame(sorted_gdp, columns=["Nation", "GDP ($B)"])
            df_gdp.index = df_gdp.index + 1 
            def highlight_player(s):
                return ['background-color: #2e8b57' if s['Nation'] == n.name else '' for v in s]
            st.dataframe(df_gdp.style.apply(highlight_player, axis=1), use_container_width=True)
            
        with rank_tab2:
            df_mil = pd.DataFrame(sorted_mil, columns=["Nation", "Power Score"])
            df_mil.index = df_mil.index + 1
            st.dataframe(df_mil.style.apply(highlight_player, axis=1), use_container_width=True)
        
        st.divider()
        st.subheader("Data Archives")
        
        if st.button("💾 Manual Save", use_container_width=True):
            save_game(st.session_state.nation, st.session_state.turn, st.session_state.messages)
            st.success("Progress archived.")

        with st.expander("📂 Manage Saved Timelines"):
            if not os.path.exists("saves"):
                st.write("No archives found.")
            else:
                save_files = [f for f in os.listdir("saves") if f.endswith('.json')]
                if not save_files:
                    st.write("Archive directory is empty.")
                else:
                    for file in save_files:
                        col1, col2, col3 = st.columns([0.5, 0.25, 0.25])
                        with col1:
                            st.caption(file.replace(".json", ""))
                        with col2:
                            if st.button("📂", key=f"load_side_{file}"):
                                with open(f"saves/{file}", "r") as f:
                                    data = json.load(f)
                                st.session_state.nation = Nation.from_dict(data["nation"])
                                st.session_state.turn = data["turn_number"]
                                st.session_state.messages = data.get("messages", [])
                                st.query_params["session"] = file.replace(".json", "")
                                st.rerun()
                        with col3:
                            if st.button("🗑️", key=f"del_side_{file}"):
                                os.remove(f"saves/{file}")
                                st.rerun()
                                
        st.divider()
        if st.button("🚪 Resign & Return to Main Menu", type="secondary", use_container_width=True):
            st.session_state.nation = None
            st.session_state.turn = 1
            st.session_state.messages = []
            st.session_state.diplomacy_chat = []
            st.query_params.clear() 
            st.rerun()

    # ==========================================
    # --- VIEW 1: THE COMMAND CENTER ---
    # ==========================================
    if st.session_state.nav_view == "💬 Command Center":
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        if st.button("🔔 End Turn"):
            event = trigger_historical_event(st.session_state.nation, st.session_state.turn, st.session_state.ai)
            if event:
                st.session_state.messages.append({"role": "assistant", "content": f"### GLOBAL EVENT: {st.session_state.turn}\n{event}"})
                apply_ai_stats(st.session_state.nation, event)
            
            old_gdp = st.session_state.nation.gdp
            gdp_growth, taxes, interest, deficit = simulate_economy(st.session_state.nation)
            pop_growth = simulate_population(st.session_state.nation)
            
            eco_data = {
                "gdp_growth_abs": gdp_growth,
                "gdp_growth_pct": round((gdp_growth / old_gdp) * 100, 2) if old_gdp > 0 else 0,
                "pop_growth": pop_growth,
                "gdp_per_capita": (st.session_state.nation.gdp * 1_000_000_000) / max(1, st.session_state.nation.population),
                "tax_revenue": taxes,
                "debt_status": "Contracted" if st.session_state.nation.debt < getattr(st.session_state, 'prev_debt', 0) else "Expanded"
            }
            st.session_state.prev_debt = st.session_state.nation.debt

            with st.spinner("Compiling National Progress Report..."):
                progress_report = st.session_state.ai.generate_state_of_the_nation(st.session_state.nation, eco_data)
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": f"## 📈 STATE OF THE NATION: {st.session_state.turn}\n\n{progress_report}"
                })
            
            st.session_state.turn += 1
            st.session_state.nation.starting_year += 1 
            st.session_state.nation.process_turn()
            
            report_msg = f"Yearly Report: +${taxes:.2f}B Taxes | -${interest:.2f}B Interest"
            if deficit > 0:
                report_msg += f" | 🚨 BORROWED ${deficit:.2f}B TO COVER DEFICIT"
                
            st.toast(report_msg)
            
            st.session_state.nation.record_stats(st.session_state.turn)
            save_game(st.session_state.nation, st.session_state.turn, st.session_state.messages)
            st.rerun()

        st.divider()
        st.markdown("### 📝 Issue Executive Directive")
        
        with st.form("directive_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                dir_type = st.selectbox("Directive Type:", ["📜 Law / Act", "🎤 Public Speech", "⚙️ Other Executive Action"])
            with col2:
                budget = st.number_input("Budget Allocation ($ Billions)", min_value=0.0, value=0.0, step=0.1, help="Type 0.3 for $300 Million.")
            
            prompt = st.text_area("Directive Details:", placeholder="Draft your policy, speech, or action here...")
            submitted = st.form_submit_button("Execute Directive ➔", type="primary")

       # THE FIX: Cleaned up the double copy-paste block!
        if submitted and prompt:
            full_command = f"**[{dir_type} | Budget: ${budget}B]**\n{prompt}"
            st.session_state.messages.append({"role": "user", "content": full_command})
            
            # REMOVED the direct nav_view modification from here!
            
            with st.chat_message("user"):
                st.markdown(full_command)
            with st.chat_message("assistant"):
                with st.spinner("Analyzing geopolitical implications (Drafting Narrative & Archiving)..."):
                    
                    st.session_state.nation.treasury -= budget
                    
                    response_story, law_summary = st.session_state.ai.parse_directive(dir_type, full_command, st.session_state.nation, st.session_state.turn)
                    
                    st.markdown(response_story)
                    apply_ai_stats(st.session_state.nation, response_story)
                    
                    st.session_state.nation.add_event(st.session_state.turn, prompt)
                    
                    if "Law" in dir_type or budget > 0:
                        st.session_state.nation.add_law(
                            st.session_state.turn, 
                            law_summary.get("name", f"{dir_type} ({st.session_state.turn})"), 
                            law_summary.get("description", "A major national directive."),
                            law_summary.get("effects", "Assorted national impacts.")
                        )
                    
                    st.session_state.messages.append({"role": "assistant", "content": response_story})
                    save_game(st.session_state.nation, st.session_state.turn, st.session_state.messages)
            
            # --- NEW JUMP FLAG ---
            st.session_state.jump_to_command = True
            st.rerun()
    # ==========================================
    # --- VIEW 2: DATA VISUALIZATION ---
    # ==========================================
    elif st.session_state.nav_view == "📊 National Analytics":
        st.subheader(f"Historical Trajectory of {st.session_state.nation.name}")
        st.subheader("National Analytics & Finance")
        
        with st.expander("💳 Central Bank & Debt Management", expanded=True):
            col1, col2 = st.columns(2)
            max_borrow_limit = max(0.0, (st.session_state.nation.gdp * 0.40) - st.session_state.nation.debt)
            
            with col1:
                st.markdown("### Borrow Funds")
                st.caption("Interest is set at 5% annually. Exceeding 40% Debt-to-GDP triggers a default.")
                
                if st.session_state.nation.debt_to_gdp_ratio >= 40:
                    st.error("🚨 **NATION IN DEFAULT** - International markets refuse to lend until debt is reduced below 40%.")
                else:
                    st.info(f"**Available Credit:** ${max_borrow_limit:,.2f}B")
                    borrow_amount = st.number_input("Amount to Borrow ($B)", min_value=0.0, max_value=max_borrow_limit, step=1.0)
                    if st.button("Issue Government Bonds", type="primary") and borrow_amount > 0:
                        st.session_state.nation.treasury += borrow_amount
                        st.session_state.nation.debt += borrow_amount
                        st.session_state.nation.add_event(st.session_state.turn, f"Issued ${borrow_amount}B in debt.")
                        save_game(st.session_state.nation, st.session_state.turn, st.session_state.messages)
                        st.rerun()

            with col2:
                st.markdown("### Repay Debt")
                st.caption("Pay down the principal debt to reduce annual interest payments.")
                max_repayment = min(st.session_state.nation.treasury, st.session_state.nation.debt)
                
                repay_amount = st.number_input("Amount to Repay ($B)", min_value=0.0, max_value=float(max_repayment), step=1.0)
                if st.button("Authorize Debt Repayment") and repay_amount > 0:
                    st.session_state.nation.treasury -= repay_amount
                    st.session_state.nation.debt -= repay_amount
                    st.session_state.nation.add_event(st.session_state.turn, f"Repaid ${repay_amount}B of national debt.")
                    save_game(st.session_state.nation, st.session_state.turn, st.session_state.messages)
                    st.rerun()
        st.divider()

        if hasattr(st.session_state.nation, 'stat_history') and st.session_state.nation.stat_history:
            df = pd.DataFrame(st.session_state.nation.stat_history)
            df.set_index("Year", inplace=True)

            colA, colB = st.columns(2)
            with colA:
                st.markdown("**Economic Indicators**")
                st.line_chart(df[["GDP ($B)", "Treasury ($B)"]])
            with colB:
                st.markdown("**National Stability**")
                st.line_chart(df[["Stability (%)", "Approval (%)"]])

            st.markdown("**Population Growth**")
            st.line_chart(df[["Population"]], color="#FF4B4B")
        else:
            st.info("Pass your first turn to begin tracking national analytics.")
    
    # ==========================================
    # --- VIEW 3: FOREIGN AFFAIRS & INTELLIGENCE ---
    # ==========================================
   # ==========================================
    # --- VIEW 3: FOREIGN AFFAIRS & INTELLIGENCE ---
    # ==========================================
    elif st.session_state.nav_view == "🌍 Foreign Affairs":
        st.subheader("Global Operations Dashboard")
        
        fa_dip, fa_esp, fa_mil = st.tabs(["🤝 Diplomacy", "🕵️ Espionage", "⚔️ Military"])
        
        available_targets = list(st.session_state.nation.world_gdp.keys())
        if hasattr(st.session_state.nation, 'regional_neighbors'):
            for neighbor in st.session_state.nation.regional_neighbors.keys():
                if neighbor not in available_targets:
                    available_targets.insert(0, neighbor) 
        if not available_targets:
            available_targets = ["United States", "China", "Russia"] 

        # ---> YOU ACCIDENTALLY DELETED THIS ENTIRE BLOCK! <---
        with fa_dip:
            col_list, col_chat = st.columns([1, 2.5])
            
            with col_list:
                st.markdown("### 📇 Contacts")
                for target in available_targets:
                    if target not in st.session_state.nation.diplomatic_chats:
                        st.session_state.nation.diplomatic_chats[target] = []
                
                chat_partner = st.radio("Select Nation:", available_targets, label_visibility="collapsed")
                
                st.markdown("---")
                st.markdown("**Chief Diplomat Status:**")
                chat_history = st.session_state.nation.diplomatic_chats[chat_partner]
                if len(chat_history) > 4:
                    st.image("Assets/Love emoji.gif", caption="Relations are active!")
                else:
                    st.image("Assets/meh.gif", caption="Awaiting instructions.")

            with col_chat:
                st.markdown(f"### 🔒 Secure Channel: {chat_partner}")
                
                # --- THE FIX: MOVED TREATY EXPANDER TO THE TOP! ---
                with st.expander(f"📜 Propose Formal Treaty with {chat_partner}"):
                    with st.form("treaty_form", clear_on_submit=True):
                        t_name = st.text_input("Treaty Name:", placeholder="e.g., The Manila-Washington Defense Pact")
                        t_duration = st.text_input("Treaty Duration:", value="Indefinite", help="e.g., 10 Years, Indefinite, 5 Turns")
                        t_context = st.text_area("Treaty Context & Terms:", placeholder="Draft the terms of the agreement, trade policies, or military alliances here...")
                        
                        t_submitted = st.form_submit_button(f"Sign & Execute Treaty ➔", type="primary")

                        if t_submitted and t_name and t_context:
                            treaty_prompt = f"**Target Nation:** {chat_partner}\n**Treaty Name:** {t_name}\n**Duration:** {t_duration}\n**Terms:** {t_context}"
                            full_command = f"**[🤝 Formal Treaty | Target: {chat_partner}]**\n{treaty_prompt}"
                            
                            st.session_state.messages.append({"role": "user", "content": full_command})
                            
                            # Auto-Route to Command Center to view results!
                            st.session_state.nav_view = "💬 Command Center"
                            st.session_state.jump_to_command = True
                            
                            with st.chat_message("user"):
                                st.markdown(full_command)
                            
                            with st.chat_message("assistant"):
                                with st.spinner("Analyzing global geopolitical shifts (Drafting Narrative & Archiving)..."):
                                    response_story, treaty_summary = st.session_state.ai.parse_directive("🤝 Formal Treaty", treaty_prompt, st.session_state.nation, st.session_state.turn)
                                    
                                    st.markdown(response_story)
                                    apply_ai_stats(st.session_state.nation, response_story)
                                    
                                    st.session_state.nation.add_treaty(
                                        st.session_state.turn, 
                                        chat_partner,
                                        treaty_summary.get("name", t_name), 
                                        t_duration,
                                        treaty_summary.get("description", t_context),
                                        treaty_summary.get("effects", "Assorted international impacts.")
                                    )
                                    
                                    st.session_state.nation.add_event(st.session_state.turn, f"Signed '{t_name}' with {chat_partner}.")
                                    st.session_state.messages.append({"role": "assistant", "content": response_story})
                                    save_game(st.session_state.nation, st.session_state.turn, st.session_state.messages)
                            st.rerun()

                # --- CHAT HISTORY RENDERS BELOW THE EXPANDER ---
                if not chat_history:
                    st.caption(f"Secure channel with {chat_partner} established. Awaiting transmission...")
                else:
                    import html as _html

                    def _esc(text: str) -> str:
                        return _html.escape(text).replace("\n", "<br />")

                    chat_html = (
                        '<div style="max-height:450px; overflow:auto; padding:12px; border:1px solid #334155; '
                        'border-radius:12px; background:#0b1220;">'
                    )

                    for role, msg in chat_history:
                        bubble_bg = "#1e293b" if role == "Supreme Leader" else "#0e3a66"
                        label = "You" if role == "Supreme Leader" else chat_partner
                        chat_html += (
                            f'<div style="margin-bottom:10px;">'
                            f'<div style="font-size:0.85rem; font-weight:600; color:#94a3b8; margin-bottom:3px;">{label}</div>'
                            f'<div style="padding:10px; border-radius:10px; background:{bubble_bg}; color:#e2e8f0; line-height:1.4;">{_esc(msg)}</div>'
                            f'</div>'
                        )

                    chat_html += "</div>"
                    st.markdown(chat_html, unsafe_allow_html=True)

                # --- CHAT INPUT SAFELY AT THE ABSOLUTE BOTTOM ---
                diplomatic_message = st.chat_input(f"Send a diplomatic cable to {chat_partner}...")
                
                if diplomatic_message:
                    with st.spinner(f"Awaiting response from {chat_partner}..."):
                        delegate_response = st.session_state.ai.negotiate(
                            st.session_state.nation.name, 
                            chat_partner, 
                            diplomatic_message, 
                            chat_history
                        )
                        
                        st.session_state.nation.diplomatic_chats[chat_partner].append(("Supreme Leader", diplomatic_message))
                        st.session_state.nation.diplomatic_chats[chat_partner].append((f"{chat_partner} Delegate", delegate_response))
                        
                        st.session_state.messages.append({"role": "user", "content": f"**[Diplomatic Cable to {chat_partner}]:** {diplomatic_message}"})
                        st.session_state.messages.append({"role": "assistant", "content": f"**[{chat_partner} Delegate]:** {delegate_response}"})
                        st.session_state.nation.add_event(st.session_state.turn, f"Diplomatic exchange with {chat_partner}.")
                        save_game(st.session_state.nation, st.session_state.turn, st.session_state.messages)
                        st.rerun()

                with fa_esp:
                    st.markdown("### 🕵️ Directorate of Intelligence")
                    intel_power = st.session_state.nation.intelligence_power
                    
                    if intel_power <= 0:
                        st.error("🚨 **NO INTELLIGENCE BUREAU DETECTED.** Your Intelligence Power is 0. Pass an Executive Directive to establish a National Intelligence Agency before attempting espionage, or your agents will be immediately captured.")
                    
                    st.metric("National Intelligence Power", f"{intel_power:,.1f}")
                    
                    esp_target = st.selectbox("Target Nation for Covert Operation:", available_targets, key="esp_target")
                    op_details = st.text_area("Operation Directives (e.g., Sabotage infrastructure, steal military blueprints):")
                    
                    risk_level = st.slider("Operation Risk Level (1 = Safe/Low Reward, 100 = Suicidal/High Reward)", 1, 100, 50)
                    
                    target_base_strength = getattr(st.session_state.nation, 'regional_neighbors', {}).get(esp_target, st.session_state.nation.world_military.get(esp_target, 200.0))
                    enemy_intel = target_base_strength * 0.25 
                    
                    intel_diff_bonus = (intel_power - enemy_intel) * 0.5
                    success_chance = 50 + intel_diff_bonus - (risk_level * 0.5)
                    success_chance = max(1.0, min(95.0, success_chance)) 
                    
                    st.caption(f"Estimated Success Probability: **{success_chance:.1f}%**")
                    
                    if st.button("Execute Operation Blacklight", type="primary"):
                        if op_details and intel_power > 0:
                            import random
                            roll = random.uniform(0, 100)
                            
                            if roll <= success_chance:
                                st.success(f"### 🟢 OPERATION SUCCESSFUL (Rolled {roll:.1f} vs {success_chance:.1f})")
                                with st.spinner("Decrypting stolen files..."):
                                    report = st.session_state.ai.run_espionage(st.session_state.nation, esp_target, f"SUCCESSFUL OPERATION: {op_details}", st.session_state.turn)
                                    st.markdown(report)
                                    
                                    if risk_level > 70:
                                        st.session_state.nation.tech_level = min(5.0, st.session_state.nation.tech_level + 0.1)
                                        st.toast("🧪 Stole advanced technological blueprints!")
                                    else:
                                        st.session_state.nation.treasury += 1.0
                                        st.toast("💰 Siphoned $1.0B from offshore accounts!")
                            else:
                                st.error(f"### 🔴 OPERATION COMPROMISED (Rolled {roll:.1f} vs {success_chance:.1f})")
                                with st.spinner("Receiving distress signal..."):
                                    report = st.session_state.ai.run_espionage(st.session_state.nation, esp_target, f"FAILED OPERATION. Agents captured. {op_details}", st.session_state.turn)
                                    st.markdown(report)
                                    
                                    st.session_state.nation.political_stability -= (risk_level * 0.2)
                                    st.session_state.nation.public_approval -= (risk_level * 0.2)
                                    st.toast("🚨 Agents captured! Major diplomatic incident!")
                            
                            st.session_state.nation.add_event(st.session_state.turn, f"[CLASSIFIED] Op against {esp_target}. Success: {roll <= success_chance}")
                            save_game(st.session_state.nation, st.session_state.turn, st.session_state.messages)
                        elif intel_power <= 0:
                            st.warning("You must establish an Intelligence Agency before executing operations.")
                        else:
                            st.warning("Please provide operation directives.")

                with fa_mil:
                    st.markdown("### ⚔️ War Room")
                    mil_target = st.selectbox("Select Target Nation:", available_targets, key="mil_target")
                    
                    st.info(f"🛡️ **Your True Combat Power:** {st.session_state.nation.combat_power:,.0f}")
                    target_base_strength = getattr(st.session_state.nation, 'regional_neighbors', {}).get(mil_target, st.session_state.nation.world_military.get(mil_target, 200.0))
                    st.write(f"📡 **Estimated Enemy Base Strength:** {target_base_strength}")
                    
                    force_commitment = st.slider("Percentage of Armed Forces to Deploy:", min_value=10, max_value=100, value=50, step=10)
                    
                    if st.button(f"⚔️ Declare War on {mil_target}", type="primary"):
                        with st.spinner(f"Mobilizing forces against {mil_target}..."):
                            war_results = st.session_state.nation.execute_war(mil_target, target_base_strength, force_commitment)
                            report = st.session_state.ai.generate_war_report(st.session_state.nation.name, mil_target, war_results, st.session_state.turn)
                            
                            if war_results['result'] == "VICTORY":
                                st.success(f"### 🏆 DECISIVE VICTORY\n{report}")
                            else:
                                st.error(f"### 💀 CRUSHING DEFEAT\n{report}")
                            
                            st.session_state.messages.append({"role": "assistant", "content": f"### ⚔️ WAR REPORT: {mil_target}\n{report}"})
                            st.session_state.nation.add_event(st.session_state.turn, f"Waged war against {mil_target}. Result: {war_results['result']}")
                            save_game(st.session_state.nation, st.session_state.turn, st.session_state.messages)
                            st.rerun()