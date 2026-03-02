import os
import json
from crewai import LLM
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from coyote_ventures_weekly_intelligence_digest___email_automation.tools.serply_news_search_safe import SerplyNewsSearchToolSafe
from coyote_ventures_weekly_intelligence_digest___email_automation.tools.supabase_write_candidates import SupabaseWriteCandidatesTool

from pydantic import BaseModel
from jambo import SchemaConverter

@CrewBase
class CoyoteVenturesWeeklyIntelligenceDigestEmailAutomationCrew:
    """CoyoteVenturesWeeklyIntelligenceDigestEmailAutomation crew"""

    
    @agent
    def healthcare_news_discovery_specialist(self) -> Agent:
        
        return Agent(
            config=self.agents_config["healthcare_news_discovery_specialist"],
            
            
            tools=[SerplyNewsSearchToolSafe(limit=5), SupabaseWriteCandidatesTool()],
            reasoning=False,
            max_reasoning_attempts=None,
            inject_date=True,
            allow_delegation=False,
            max_iter=50,
            max_rpm=None,
            
            max_execution_time=None,
            llm=LLM(
                model="openai/gpt-4o-mini",
                temperature=0.4,
                max_tokens=16384,
            ),
            response_format=self._load_response_format("healthcare_news_discovery_specialist"),
        )
    
    @task
    def search_for_candidate_articles(self) -> Task:
        return Task(
            config=self.tasks_config["search_for_candidate_articles"],
            markdown=False,
            
            
        )
    
    @crew
    def crew(self) -> Crew:
        """Discovery-only crew. Evaluation is handled by the direct Python pipeline in main.py."""
        discovery_agent = self.healthcare_news_discovery_specialist()
        search_task = self.search_for_candidate_articles()
        return Crew(
            agents=[discovery_agent],
            tasks=[search_task],
            process=Process.sequential,
            verbose=True,
            chat_llm=LLM(model="openai/gpt-4o-mini"),
        )


    def _load_response_format(self, name):
        with open(os.path.join(self.base_directory, "config", f"{name}.json")) as f:
            json_schema = json.loads(f.read())

        return SchemaConverter.build(json_schema)

