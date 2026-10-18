import os
from google.adk.agents import Agent
from google.genai import types
from google.adk.skills import load_skill_from_dir, models
from google.adk.tools.skill_toolset import SkillToolset
from google.adk.apps import App

from dotenv import load_dotenv
load_dotenv()


seo_skill = models.Skill(
    frontmatter=models.Frontmatter(
        name="seo-checklist",
        description=(
            "SEO optimization checklist for blog posts. Covers title tags,"
            " meta descriptions, heading structure, keyword placement,"
            " and readability best practices."
        ),
    ),
    instructions=(
        "When optimizing a blog post for SEO, check each item:\n\n"
        "1. **Title**: 50-60 chars, primary keyword near the start\n"
        "2. **Meta description**: 150-160 chars, includes a call-to-action\n"
        "3. **Headings**: H2/H3 hierarchy, keywords in 2-3 headings\n"
        "4. **First paragraph**: Primary keyword in first 100 words\n"
        "5. **Keyword density**: 1-2%, never forced or awkward\n"
        "6. **Paragraphs**: 2-3 sentences max, use bullet lists often\n"
        "7. **Links**: 2-3 internal + 3-5 external to authoritative sources\n"
        "8. **Images**: Alt text with keywords, compressed, descriptive names\n"
        "9. **URL slug**: Short, keyword-rich, hyphenated\n\n"
        "Review the content against each item and suggest specific improvements."
    ),
)

skill_toolset = SkillToolset(
    skills=[
        seo_skill
    ]
)

root_agent = Agent(
    model="gemini-3.8-flash",
    name="blog_skills_agent",
    description="A blog-writing agent powered by reusable skills.",
    instruction=(
        "You are a blog-writing assistant with specialized skills.\n\n"
        "You have the following skills available:\n"
        "- **seo-checklist**: SEO optimization rules (load for SEO review)\n"
        "When the user asks you to write, research, or optimize a blog post:\n"
        "1. Load the relevant skill(s) to get detailed instructions\n"
        "2. Follow the skill's step-by-step instructions\n"
        "3. Apply multiple skills together when appropriate\n\n"
        "Always explain which skill you're using and why."
    ),
    tools=[skill_toolset],
)