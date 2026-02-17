import os
import json
from crewai import LLM
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import (
	ScrapeWebsiteTool,
	SerplyNewsSearchTool
)
from coyote_ventures_weekly_intelligence_digest___email_automation.tools.article_extractor import ArticleExtractorTool
from coyote_ventures_weekly_intelligence_digest___email_automation.tools.thesis_article_comparison_tool import ThesisArticleComparisonTool
from coyote_ventures_weekly_intelligence_digest___email_automation.tools.supabase_write_candidates import SupabaseWriteCandidatesTool
from coyote_ventures_weekly_intelligence_digest___email_automation.tools.supabase_read_candidates import SupabaseReadCandidatesTool
from coyote_ventures_weekly_intelligence_digest___email_automation.tools.supabase_write_content import SupabaseWriteContentTool
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
            
            
            tools=[SerplyNewsSearchTool(limit=5), SupabaseWriteCandidatesTool()],
            reasoning=False,
            max_reasoning_attempts=None,
            inject_date=True,
            allow_delegation=False,
            max_iter=25,
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
    def article_harvester(self) -> Agent:
        
        return Agent(
            config=self.agents_config["article_harvester"],
            
            
            tools=[SupabaseReadCandidatesTool(), ArticleExtractorTool(), SupabaseWriteContentTool()],
            reasoning=False,
            max_reasoning_attempts=None,
            inject_date=True,
            allow_delegation=False,
            max_iter=25,
            max_rpm=None,
            
            max_execution_time=None,
            llm=LLM(
                model="openai/gpt-4o-mini",
                temperature=0.4,
            ),
            
        )
    
    @agent
    def thesis_relevance_judge(self) -> Agent:
        
        return Agent(
            config=self.agents_config["thesis_relevance_judge"],
            
            
            tools=[
                ScrapeWebsiteTool(website_url="https://www.coyote.ventures/thesis"),
                ThesisArticleComparisonTool(),
                SupabaseWriteEvaluationsTool(),
            ],
            reasoning=False,
            max_reasoning_attempts=None,
            inject_date=True,
            allow_delegation=False,
            max_iter=25,
            max_rpm=None,
            
            max_execution_time=None,
            llm=LLM(
                model="openai/gpt-4o-mini",
                temperature=0.7,
            ),
            
        )
    

    
    @task
    def search_for_candidate_articles(self) -> Task:
        return Task(
            config=self.tasks_config["search_for_candidate_articles"],
            markdown=False,
            
            
        )
    
    @task
    def extract_article_content(self) -> Task:
        return Task(
            config=self.tasks_config["extract_article_content"],
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


    def _load_response_format(self, name):
        with open(os.path.join(self.base_directory, "config", f"{name}.json")) as f:
            json_schema = json.loads(f.read())

        return SchemaConverter.build(json_schema)

