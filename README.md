# Coyote Ventures Weekly Intelligence Digest Email Automation

Welcome to the Coyote Ventures Weekly Intelligence Digest Email Automation Crew project, powered by [crewAI](https://crewai.com).

Current Workflow:
Web scraping API (Serply) scrapes thesis-relevant articles from Google News
Uses a ChatGPT API to evaluate article titles against core thesis pillars
An external email services generates emails delivered directly to inboxes
Slack integration for on-demand news updates and queries

Pipeline Overview

Web Scraping:
The current process begins with a web scraping API called Serply.io, which scrapes the internet according to a set list of keywords, listed below. The keywords are already time filtered, ensuring that only new articles are being scraped in the first place. These articles are then inserted into a storage system of data tables managed by Supabase.com, which is where we will be reading data from later.

Article Evaluation Against Thesis:
To evaluate all article titles against the thesis, we will use an OpenAI API and API key, specifically the gpt-4.1 mini model of ChatGPT. The process involves reading 5 articles from the database that we were inserting articles into, pulling the title information, and scoring the title against a summary of the core pillars of the thesis. The evaluations generate a relevance score, a confidence score, focus area relevant to the thesis, an “executive summary”, and a “why this matters”. 

Email Generation:
The email generation process involves looking at the overall table, now with full article information (url, title, relevance score, publication date, summary, etc) and pulls the first 7-10  articles (can edit number later) with the highest relevancy and the status that it hasn’t been set in the email digest yet. After the creation of the article, articles are marked with the characteristic that they have been sent, so repeated articles should not occur.



## Installation

Ensure you have Python >=3.10 <3.14 installed on your system. This project uses [UV](https://docs.astral.sh/uv/) for dependency management and package handling, offering a seamless setup and execution experience.

First, if you haven't already, install uv:

```bash
pip install uv
```

Next, navigate to your project directory and install the dependencies:

(Optional) Lock the dependencies and install them by using the CLI command:
```bash
crewai install
```
### Customizing

**Add your `OPENAI_API_KEY` into the `.env` file**

- Modify `src/coyote_ventures_weekly_intelligence_digest___email_automation/config/agents.yaml` to define your agents
- Modify `src/coyote_ventures_weekly_intelligence_digest___email_automation/config/tasks.yaml` to define your tasks
- Modify `src/coyote_ventures_weekly_intelligence_digest___email_automation/crew.py` to add your own logic, tools and specific args
- Modify `src/coyote_ventures_weekly_intelligence_digest___email_automation/main.py` to add custom inputs for your agents and tasks

## Running the Project

To kickstart your crew of AI agents and begin task execution, run this from the root folder of your project:

```bash
$ crewai run
```

This command initializes the coyote_ventures_weekly_intelligence_digest___email_automation Crew, assembling the agents and assigning them tasks as defined in your configuration.

This example, unmodified, will run the create a `report.md` file with the output of a research on LLMs in the root folder.

## Understanding Your Crew

The coyote_ventures_weekly_intelligence_digest___email_automation Crew is composed of multiple AI agents, each with unique roles, goals, and tools. These agents collaborate on a series of tasks, defined in `config/tasks.yaml`, leveraging their collective skills to achieve complex objectives. The `config/agents.yaml` file outlines the capabilities and configurations of each agent in your crew.

## Support

For support, questions, or feedback regarding the CoyoteVenturesWeeklyIntelligenceDigestEmailAutomation Crew or crewAI.
- Visit our [documentation](https://docs.crewai.com)
- Reach out to us through our [GitHub repository](https://github.com/joaomdmoura/crewai)
- [Join our Discord](https://discord.com/invite/X4JWnZnxPb)
- [Chat with our docs](https://chatg.pt/DWjSBZn)

Let's create wonders together with the power and simplicity of crewAI.
