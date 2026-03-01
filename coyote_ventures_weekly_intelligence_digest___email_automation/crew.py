import os
import json
from crewai import LLM
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from coyote_ventures_weekly_intelligence_digest___email_automation.tools.serply_news_search_safe import SerplyNewsSearchToolSafe
from coyote_ventures_weekly_intelligence_digest___email_automation.tools.thesis_title_relevance_tool import ThesisTitleRelevanceTool
from coyote_ventures_weekly_intelligence_digest___email_automation.tools.supabase_write_candidates import SupabaseWriteCandidatesTool
from coyote_ventures_weekly_intelligence_digest___email_automation.tools.supabase_read_candidates import SupabaseReadCandidatesTool
from coyote_ventures_weekly_intelligence_digest___email_automation.tools.supabase_write_evaluations import SupabaseWriteEvaluationsTool

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
    
    @agent
    def thesis_relevance_judge(self) -> Agent:
        
        return Agent(
            config=self.agents_config["thesis_relevance_judge"],
            
            
            tools=[
                SupabaseReadCandidatesTool(),
                ThesisTitleRelevanceTool(),
                SupabaseWriteEvaluationsTool(),
            ],
            reasoning=False,
            max_reasoning_attempts=None,
            inject_date=True,
            allow_delegation=False,
            max_iter=15,
            max_rpm=None,

            max_execution_time=None,
            llm=LLM(
                model="openai/gpt-4.1-mini",
                temperature=0.3,
                max_tokens=16384,
            ),

        )
    

    
    @task
    def search_for_candidate_articles(self) -> Task:
        return Task(
            config=self.tasks_config["search_for_candidate_articles"],
            markdown=False,
            
            
        )
    
    @task
    def evaluate_investment_relevance(self) -> Task:
        return Task(
            config=self.tasks_config["evaluate_investment_relevance"],
            markdown=False,
            
            
        )
    

    @crew
    def crew(self) -> Crew:
        """Creates the CoyoteVenturesWeeklyIntelligenceDigestEmailAutomation crew"""
        return Crew(
            agents=self.agents,  # Automatically created by the @agent decorator
            tasks=self.tasks,  # Automatically created by the @task decorator
            process=Process.sequential,
            verbose=True,
            chat_llm=LLM(model="openai/gpt-4o-mini"),
        )

    def crew_judge_only(self) -> Crew:
        """Crew with only the thesis_relevance_judge and evaluate task. Use to test the judge without running Discovery."""
        judge = self.thesis_relevance_judge()
        cfg = self.tasks_config["evaluate_investment_relevance"]
        eval_task = Task(
            description=cfg["description"],
            expected_output=cfg["expected_output"],
            agent=judge,
            context=[],  # no dependency on search task
            markdown=False,
        )
        return Crew(
            agents=[judge],
            tasks=[eval_task],
            process=Process.sequential,
            verbose=True,
            chat_llm=LLM(model="openai/gpt-4o-mini"),
        )


    def _load_response_format(self, name):
        with open(os.path.join(self.base_directory, "config", f"{name}.json")) as f:
            json_schema = json.loads(f.read())

        return SchemaConverter.build(json_schema)

