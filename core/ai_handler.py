# core/ai_handler.py
import json
import time
import os
import streamlit as st
import re
from dotenv import load_dotenv
from openai import OpenAI, RateLimitError

class AIHandler:
    def __init__(self, use_local=True):
        load_dotenv()
        
        # --- 1. SAFELY GET THE API KEY ---
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            try:
                api_key = st.secrets["OPENROUTER_API_KEY"]
            except KeyError:
                print("[SYSTEM ERROR]: API Key not found in OS or st.secrets!")
                
        # --- 2. ALWAYS INITIALIZE THE CLOUD ENGINE ---
        self.cloud_client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key, 
            default_headers={
                "HTTP-Referer": "https://nacio-simulator.local",
                "X-Title": "Nacio: A Global Symphony",
            }
        )
        self.cloud_model = "meta-llama/llama-3.3-70b-instruct:free" 
        
        # --- 3. SET UP THE LOCAL ENGINE (OR CLOUD MIRROR) ---
        self.use_local = use_local
        if self.use_local:
            self.local_client = OpenAI(
                base_url="http://localhost:11434/v1",
                api_key="ollama", # Placeholder for local
            )
            self.local_model = "llama3.2"
            print("[SYSTEM LOG]: 🌐 HYBRID MODE ENGAGED. Cloud Initialization / Local Gameplay.")
        else:
            # If use_local is False, we just point the local variables to the cloud!
            self.local_client = self.cloud_client
            self.local_model = self.cloud_model
            print("[SYSTEM LOG]: ☁️ CLOUD MODE ENGAGED. All generation via OpenRouter.")

    def _call_api(self, prompt, retries=3, force_cloud=False): 
        """Routes the prompt to either the Cloud or Local AI based on the task."""
        client_to_use = self.cloud_client if force_cloud else self.local_client
        model_to_use = self.cloud_model if force_cloud else self.local_model
        
        for attempt in range(retries):
            try:
                response = client_to_use.chat.completions.create(
                    model=model_to_use,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7
                )
                return response.choices[0].message.content.strip()
                
            except RateLimitError:
                print(f"\n[SYSTEM LOG]: Rate limit hit. Waiting 5 seconds...")
                time.sleep(5)
                continue
            except Exception as e:
                return f"[UPLINK ERROR]: {str(e)}"
                
        return "[SYSTEM ERROR]: Maximum retries reached. The AI Cabinet is unavailable."

    def generate_starting_nation(self, country_name, year):
        """Asks the AI for stats, with key normalization and world rank failovers."""
        archive_path = "historical_archive.json"
        clean_name = country_name.strip()
        lookup_key = f"{clean_name}-{year}"

        if os.path.exists(archive_path):
            with open(archive_path, "r") as f:
                archive = json.load(f)
                found_key = None
                if lookup_key in archive:
                    found_key = lookup_key
                else:
                    for existing_key in archive.keys():
                        if existing_key.replace(" ", "") == lookup_key.replace(" ", ""):
                            found_key = existing_key
                            break
                
                if found_key:
                    print(f"[SYSTEM LOG]: Match found! Loading {found_key}...")
                    data = archive[found_key]
                    if "world_gdp" not in data:
                        data["world_gdp"] = {"United States": 10000.0, "China": 1000.0, "Japan": 5000.0}
                    if "world_military" not in data:
                        data["world_military"] = {"United States": 950.0, "Russia": 800.0, "China": 700.0}
                    if "tech_level" not in data: data["tech_level"] = 1
                    if "industrialization_level" not in data: data["industrialization_level"] = 1
                    if "regional_neighbors" not in data: data["regional_neighbors"] = {}
                    return data

        print(f"[SYSTEM LOG]: {lookup_key} not in archives. Requesting CLOUD AI generation...")
        
        system_prompt = f"""
        You are the world-building engine for 'Nacio: A Global Symphony'.
        Leader: {country_name}, Year: {year}.
        
        Provide realistic starting statistics based on real historical data for {year}.
        Generate the Top 10 highest GDPs and Top 10 Militaries in the world for {year} (exclude {country_name}).
        Write a 3-4-paragraph 'Initial Cabinet Report' on the immediate challenges.
        
        CRITICAL INSTRUCTION: Respond ONLY with a valid, raw JSON object. Do not include markdown formatting, backticks, or conversational text. 
        Use exactly this format and data types:
        {{
            "flag_emoji": "🇯🇵",
            "population": 116000000,
            "gdp": 1100.0,
            "treasury": 220.0,
            "debt": 150.0,
            "economic_growth_rate": 3.5,
            "military_strength": 400.0,
            "political_stability": 80.0,
            "industrialization_level": 4,
            "tech_level": 4,
            "briefing": "Narrative text goes here...",
            "regional_neighbors": {{"South Korea": 300.0, "China": 500.0}},
            "world_gdp": {{"United States": 2860.0, "Soviet Union": 1200.0}},
            "world_military": {{"United States": 950.0, "Soviet Union": 900.0}}
        }}
        """
        response_text = self._call_api(system_prompt, force_cloud=True)
        
        if "[UPLINK ERROR]" in response_text or "[SYSTEM ERROR]" in response_text:
            return response_text
            
        response_text = response_text.replace("```json", "").replace("```", "").strip()
            
        match = re.search(r'(\{.*\})', response_text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                new_clean_key = f"{clean_name}-{year}"
                
                if not os.path.exists(archive_path):
                    with open(archive_path, "w") as f: json.dump({}, f)
                with open(archive_path, "r+") as f:
                    archive = json.load(f)
                    archive[new_clean_key] = data
                    f.seek(0); json.dump(archive, f, indent=4); f.truncate()
                
                return data
            except json.JSONDecodeError as e:
                print(f"[DEBUG]: Failed to parse JSON. AI Output was: {match.group(1)}")
                return "[SYSTEM ERROR]: The AI provided an invalid data format."
                
        return "[SYSTEM ERROR]: Failed to extract data from the AI response."

    def parse_directive(self, directive_type, directive_text, nation, turn_number):
        """Pipelines the directive into Evaluation, Narrative, Stats, and Summary."""
        
        # ==========================================
        # CHUNK 0: THE POLICY JUDGE
        # ==========================================
        judge_prompt = f"""
        You are the Chief Policy Analyst of {nation.name} in {turn_number}.
        CURRENT STATE POWER INDEX (Government Competence/Stability): {nation.state_power_index:.1f} / 100.0
        Proposed Directive: "{directive_text}"
        
        Evaluate how successfully this directive can be implemented based on the State Power Index.
        Respond with EXACTLY ONE of the following tiers, and absolutely nothing else:
        UNSUCCESSFUL
        PARTIALLY WORKING
        ACCEPTABLE
        SUCCESSFUL
        VERY SUCCESSFUL
        EXTREMELY SUCCESSFUL
        """
        success_tier = self._call_api(judge_prompt).strip().upper()
        
        valid_tiers = ["UNSUCCESSFUL", "PARTIALLY WORKING", "ACCEPTABLE", "SUCCESSFUL", "VERY SUCCESSFUL", "EXTREMELY SUCCESSFUL"]
        if not any(tier in success_tier for tier in valid_tiers):
            success_tier = "ACCEPTABLE"
        else:
            for tier in valid_tiers:
                if tier in success_tier:
                    success_tier = tier
                    break

        # ==========================================
        # CHUNK 1: THE IMMERSIVE STORYTELLER
        # ==========================================
        story_prompt = f"""
        You are the simulation engine for 'Nacio'. Lead: {nation.name}, Year: {turn_number}.
        Action Type: {directive_type}
        New Directive: "{directive_text}"
        
        CRITICAL ENGINE EVALUATION: The Policy AI has evaluated this law and its outcome is: **[{success_tier}]**.
        
        CRITICAL INSTRUCTION: Write a highly detailed historical narrative perfectly matching the [{success_tier}] outcome. 
        REPLACE all bracketed placeholders (like [Name of Department]) with realistic, invented names suitable for the country! Do NOT print the brackets literally.
        
        Do NOT write a title. Start your output immediately with this EXACT format:
        **Narrative Impact:**
        [Write 2-3 paragraphs of deep socio-political and economic storytelling here]
        
        **🏛️ Internal Reactions:**
        * **[Name of Relevant Government Dept]:** [Reaction matching the tier]
        * **[Name of Social Class or Faction]:** [Reaction matching the tier]
        
        **🌍 Global Reactions:**
        * **[Name of Foreign Nation]:** [Geopolitical response]
        """
        raw_story = self._call_api(story_prompt)
        story_report = f"### 📜 Directive Analysis\n**Execution Result:** {success_tier}\n\n{raw_story}"

        # ==========================================
        # CHUNK 2: THE MATHEMATICIAN (Stats Only)
        # ==========================================
        stats_prompt = f"""
        You are the strict mathematical simulation engine for 'Nacio'.
        Calculate the exact statistical changes for the nation of {nation.name}.
        
        CURRENT NATION STATS:
        - GDP: ${nation.gdp:,.2f}B
        - Military Strength: {nation.military_strength:,.1f}
        - Political Stability: {nation.political_stability}%
        - Public Approval: {nation.public_approval}%
        - Tech Level: {nation.tech_level}/5.0
        - Ind Level: {nation.industrialization_level}/5.0
        - Economic Growth: {nation.economic_growth_rate}%
        
        NARRATIVE TO ANALYZE:
        {raw_story}
        
        CRITICAL RULES:
        1. The directive was graded as [{success_tier}]. If SUCCESSFUL, overall stats MUST be positive. If UNSUCCESSFUL, they MUST be negative.
        2. ROUNDING RULE: You MUST round all outputs to exactly 1 or 2 decimal places (e.g., 2.5, -1.25, 0.05). NEVER output microscopic fractions like 0.00000001 or 5.150000001.
        3. BOUNDARY RULE: Keep the numbers realistic based on the directive's budget.
        4. Do NOT output a 'Population' stat. Population is handled separately.
        5. Do not add conversational text. Output ONLY the bullet points.
        
        Use EXACTLY this format with realistic numbers:
        * **GDP:** [Float change, e.g., 1.50 or -0.50]
        * **Military Strength:** [Float change, e.g., 2.0 or 0.0]
        * **Political Stability:** [Float change, e.g., 5.0 or -3.0]
        * **Public Approval:** [Float change, e.g., 4.5 or -2.5]
        * **Tech Level:** [Float change, e.g., 0.10 or 0.0]
        * **Ind Level:** [Float change, e.g., 0.05 or 0.0]
        * **Economic Growth:** [Float change, e.g., 0.25 or -0.10]
        """
        raw_stats = self._call_api(stats_prompt)
        stats_report = f"**Statistical Impact:**\n{raw_stats}"

        # ==========================================
        # CHUNK 3: THE NATIONAL ARCHIVIST (Summarizer)
        # ==========================================
        archive_prompt = f"""
        Extract a highly condensed summary of the following directive for the National Archives.
        Directive: {directive_text}
        
        Respond EXACTLY in this format:
        Law Name: [Short Title]
        Description: [1 sentence]
        Effects: [Short list]
        """
        summary_text = self._call_api(archive_prompt)
        
        law_name = f"Executive Action ({turn_number})"
        law_desc = "Administrative policy implemented."
        law_eff = "Assorted impacts."
        
        for line in summary_text.split('\n'):
            line = line.strip()
            if line.startswith("Law Name:"): law_name = line.replace("Law Name:", "").replace("**", "").strip()
            elif line.startswith("Description:"): law_desc = line.replace("Description:", "").replace("**", "").strip()
            elif line.startswith("Effects:"): law_eff = line.replace("Effects:", "").replace("**", "").strip()

        summary_dict = {
            "name": law_name,
            "description": f"[{success_tier}] {law_desc}",
            "effects": law_eff
        }

        full_ui_report = story_report + "\n\n" + stats_report
        return full_ui_report, summary_dict
    
    def run_espionage(self, player_nation, target_nation, operation_details, turn_number):
        system_prompt = f"Director of Intelligence report for {player_nation.name} against {target_nation}. Operation details: {operation_details}"
        return self._call_api(system_prompt)

    def negotiate(self, player_nation_name, target_nation, player_message, chat_history):
        history_text = ""
        for sender, msg in chat_history:
            history_text += f"{sender}: {msg}\n"
            
        system_prompt = f"""
        You are the Chief Diplomat representing {target_nation}.
        You are currently in a secure negotiation with the Supreme Leader of {player_nation_name}.
        
        Previous Conversation Context:
        {history_text}
        
        Supreme Leader of {player_nation_name} says: "{player_message}"
        
        Respond in character as the diplomat of {target_nation}. Be strategic, realistic, and protective of your own nation's interests. Keep the response to 1 or 2 paragraphs.
        """
        return self._call_api(system_prompt)

    def generate_event(self, nation, year):
        if year >= 2026: return None
        
        system_prompt = f"""
        Identify a SIGNIFICANT REAL-WORLD HISTORICAL EVENT that occurred in {year}.
        Analyze how this event specifically impacts {nation.name}.
        
        Output format:
        Event Title: [Official Historical Name]
        Historical Context: [2-3 sentences explaining the global situation in {year}]
        Impact on {nation.name}: [How this specifically affects the player's country]
        
        CRITICAL STAT RULES: You MUST use ONLY these exact stat names for the Statistical Updates section:
        Statistical Updates:
        * **Population:** [Raw integer. Use negative for deaths/emigration, positive for growth]
        * **GDP:** [Raw float in Billions. Use negative for economic loss, positive for gains]
        * **Military Strength:** [Raw float change]
        * **Political Stability:** [Raw float change]
        * **Public Approval:** [Raw float change]
        * **Tech Level:** [Raw float change, max 0.1 increments]
        * **Ind Level:** [Raw float change, max 0.1 increments]
        * **Economic Growth:** [Raw float change. Use negative if slowing the economy, positive if stimulating]
        """
        return self._call_api(system_prompt)

    def generate_war_report(self, player_nation, target_nation, war_results, current_year):
        system_prompt = f"""
        You are the Supreme Commander of {player_nation}'s Armed Forces in the year {current_year}.
        We have just engaged in a massive war against {target_nation}.
        Here is the mathematically determined outcome from the simulation engine:
        - Result: {war_results['result']}
        - Our Combat Power on the field: {war_results['player_power']}
        - Enemy Combat Power on the field: {war_results['enemy_power']}
        
        Write a thrilling, realistic 2-paragraph military After Action Report (AAR) summarizing the campaign, the tactics used, and the aftermath. 
        CRITICAL: Ensure all dates in the report match the year {current_year}. Frame the narrative to match the {war_results['result']} using military terminology appropriate for the year {current_year}.
        CRITICAL: Output ONLY pure Markdown text. Do NOT output JSON.
        """
        return self._call_api(system_prompt)

    def generate_state_of_the_nation(self, nation, eco_data):
        """Generates a highly immersive annual report focusing on the last 3 years of laws."""
        final_report = f"### 📅 The Year in Review: {nation.starting_year}\n\n"
        
        # CHUNK 1: THE ATMOSPHERIC OVERVIEW
        overview_prompt = f"""
        You are the Chief of Staff reporting directly to the Supreme Leader of {nation.name}. 
        The year is STRICTLY {nation.starting_year}. 
        
        STATS: 
        - GDP: ${nation.gdp:,.2f}B (Growth: {eco_data['gdp_growth_pct']}%)
        - Stability: {nation.political_stability}%
        - Approval: {nation.public_approval}%
        
        Write 2 highly immersive, atmospheric paragraphs summarizing the political and economic climate of the nation this year. 
        Describe the mood of the citizens based on the Stability and Approval ratings. 
        Tone: Dramatic, respectful, and slightly weary from the burdens of governance.
        CRITICAL: Do NOT use markdown headers, just output the raw narrative text.
        """
        final_report += self._call_api(overview_prompt) + "\n\n"
        
        # CHUNK 2: THE 3-YEAR LEGISLATIVE DEEP DIVE
        final_report += "### 📜 Legislative Progress Report (Last 3 Years)\n\n"
        
        # THE FIX: Filter laws to only include the last 3 years!
        recent_laws = [l for l in nation.active_laws if int(l['year']) >= (int(nation.starting_year) - 3)]
        
        if not recent_laws:
            final_report += "*No major legislations or executive directives were enacted in the last 3 years.*\n\n"
        else:
            chunk_size = 2
            for i in range(0, len(recent_laws), chunk_size):
                law_chunk = recent_laws[i:i + chunk_size]
                
                # Feed the AI our clean, summarized database entries!
                law_text = "\n".join([f"- Title: {l['title']} (Enacted: {l['year']})\n  Function: {l.get('description', '')}\n  Original Impact: {l.get('effect', '')}" for l in law_chunk])
                
                law_prompt = f"""
                You are the Chief of Staff in {nation.name} in the year {nation.starting_year}.
                
                Evaluate the current status of these specific legislations passed recently:
                {law_text}
                
                For EACH law, write a flavorful, realistic progress update (1 thick paragraph per law). 
                Tell a story: Is it succeeding beautifully? Is it facing severe local corruption? Is there public pushback or logistical delays? Invent realistic political outcomes based on the function.
                
                CRITICAL: Use a bullet point with the law's title in bold, followed by the story. Do NOT write an intro or outro.
                """
                final_report += self._call_api(law_prompt) + "\n\n"

        # CHUNK 3: THE STRATEGIC COUNSEL
        final_report += "### 🎯 Chief of Staff's Counsel\n\n"
        
        advice_prompt = f"""
        You are the Chief of Staff in {nation.name} in the year {nation.starting_year}.
        STATS: Treasury: ${nation.treasury:,.2f}B | Debt: ${nation.debt:,.2f}B | Stability: {nation.political_stability}%
        
        Provide 3 strategic, highly specific recommendations for the Supreme Leader for the upcoming year based on these stats.
        
        CRITICAL: Format as a markdown list. Use a short, catchy bold title for each point, followed by 1 or 2 sentences of actionable advice. Do NOT write an intro or outro.
        """
        final_report += self._call_api(advice_prompt)
        
        return final_report