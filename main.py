import os
import json
import time
import feedparser  # Add this import for RSS parsing
from dateutil import parser
from openai import OpenAI
from langchain_community.document_loaders import PyMuPDFLoader
from textwrap import dedent
import json
import ast
import random
import tqdm
from dotenv import load_dotenv
import pandas as pd
import requests
import networkx as nx
import matplotlib.pyplot as plt
from datetime import datetime

from mongo_adapter import MongoAdapter
from response_objects import BloombergResponseObject, FMPResponseObject, FMPPressReleaseResponseObject
from email_sender import send_email



load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai_client = OpenAI(
    api_key=OPENAI_API_KEY,
)

mongo_adapter = MongoAdapter(
        connection_string="mongodb://localhost:27017",
        database_name="tmcc-news"
    )

URLS = {
    "bloomberg": [
        "https://feeds.bloomberg.com/markets/news.rss",
        "https://feeds.bloomberg.com/economics/news.rss",
        "https://feeds.bloomberg.com/technology/news.rss",
        "https://feeds.bloomberg.com/green/news.rss"
    ],
    "fmp": [
        "https://financialmodelingprep.com/api/v4/stock-news-sentiments-rss-feed?page=0&apikey=tSJPBoMv79Baig8DXj50Oky1p4oQbyhU",
        "https://financialmodelingprep.com/api/v4/general_news?page=0&apikey=tSJPBoMv79Baig8DXj50Oky1p4oQbyhU",
        "https://financialmodelingprep.com/api/v3/stock_news?page=0&apikey=tSJPBoMv79Baig8DXj50Oky1p4oQbyhU",
    ],
    "fmp_press_releases": [
        "https://financialmodelingprep.com/api/v3/press-releases?page=0&apikey=tSJPBoMv79Baig8DXj50Oky1p4oQbyhU"
    ]
}

SOURCE_TO_RESPONSE_OBJECT_MAP = {
    "bloomberg": BloombergResponseObject,
    "fmp": FMPResponseObject,
    "fmp_press_releases": FMPPressReleaseResponseObject
}

def determine_direct_ticker_companies_mentioned(title, summary):
    """
    Analyze text to extract mentioned tickers and companies.
    """
    prompt = f"""Analyze the following news article title and summary to identify stock tickers and company names mentioned:

    Title: {title}
    Summary: {summary}

    Return your response as a JSON with two keys:
    1. "tickers_mentioned": list of stock tickers mentioned (use actual tickers, not made up ones)
    2. "companies_mentioned": list of company names mentioned

    Only include directly mentioned companies and tickers, do not infer or speculate."""

    try:
        response = openai_client.chat.completions.create(
            model="o1",
            messages=[
                {"role": "system", "content": "You are a financial analyst expert at identifying company names and stock tickers in text. Return only valid tickers."},
                {"role": "user", "content": prompt}
            ],
            response_format={ "type": "json_object" }
        )
        return json.loads(response.choices[0].message.content.strip())
    except Exception as e:
        return {"tickers_mentioned": [], "companies_mentioned": []}
    

def invoke_question_prompter(title, summary, companies_tickers):
    """
    Generate relevant questions based on the article and identified companies/tickers.
    """
    prompt = f"""You are a fincancial research expert. Given a news headline and a corresponding description, your job is to generate thought-provoking and relevant research questions consistent with the implications around the headline. These questins will then be handed to financial analysts who will then surface answers consisting of the corresponding relevant companies which will be evaluated as potential trade / investment candidates.
    

    Title: {title}
    Summary: {summary}

    Generate questions about:
    1. Which tickers related to certain details contained in the headline might be relevant.
    2. Any 3rd or 4th order implications around supply chain effects or downstream effects.
    3. Sector-wide implications
    4. Trading opportunities or risks

    Return the questions as a JSON array."""

    try:
        response = openai_client.chat.completions.create(
            model="o1",
            messages=[
                {"role": "system", "content": "You are a financial analyst expert at formulating precise questions about market implications."},
                {"role": "user", "content": prompt}
            ],
            response_format={ "type": "json_object" }
        )
        return json.loads(response.choices[0].message.content.strip())["questions"]
    except Exception as e:
        print(f"Error in invoke questions: {e}")
        return []
    

def invoke_answer_worker(question, title, summary, companies_tickers):
    """
    Answer a specific question about market implications.
    """
    
    prompt = dedent(f"""
    You are an elite quantitative analyst at one of the world's top hedge funds. Your expertise lies in rapidly analyzing market-moving events and tertiary impacts on specific stocks and sectors. You have deep knowledge of market dynamics, company fundamentals, and how various economic factors interplay to affect companies fundamentally.

    For each question, your task is to identify the specific U.S. stocks (by their ticker) that suffciently answer the question supplied in the context of investment and trading opportunities and to provide precise reasoning for that the ticker is relevant. Your analysis will be used for immediate trading decisions, so accuracy and clarity are crucial. For every relevant in-depth reasoning around a ticker you make, you earn a $1,000,000 bonus.

    {question}

    Rules for Analysis:
    2. Focus on both obvious first-order effects and less obvious second/third-order impacts
    3. Consider competitive dynamics and industry structure

    Give me the exact tickers and reasoning in JSON.

    RESPOND WITH RAW JSON ONLY. NO MARKDOWN. NO EXPLANATION. NO FORMATTING.

    Required format:
    {{
        "tickers": [
            {{
                "symbol": "TICKER",
                "reasoning": "Brief explanation of why"
            }}
        ]
    }}
    """).strip()

    try:
        response = openai_client.chat.completions.create(
            model="o1",
            messages=[
                {"role": "system", "content": "You are a financial analyst providing specific market analysis. Only use real stock tickers."},
                {"role": "user", "content": prompt}
            ],
            response_format={ "type": "json_object" }
        )
        return json.loads(response.choices[0].message.content.strip())
    except Exception as e:
        return {"tickers": [], "reason": []}
    

def invoke_evaluation_judge(merged_analysis, title, summary):
    """
    Evaluate and refine the merged analysis from answer workers.
    """
    prompt = f"""Review and evaluate this merged analysis of a financial news article:

    Title: {title}
    Summary: {summary}

    Merged Analysis:
    {json.dumps(merged_analysis, indent=2)}

    Evaluate the analysis and return a refined JSON with:
    1. "tickers": list of the most relevant tickers (remove any that aren't strongly justified)
    2. "reason": list of the most important and well-justified reasons

    Return your evaluation as a JSON object. Remove any speculative or weakly supported points."""

    try:
        response = openai_client.chat.completions.create(
            model="o1",
            messages=[
                {"role": "system", "content": "You are a senior financial analyst evaluating market analysis. Be critical and only keep well-justified points."},
                {"role": "user", "content": prompt}
            ],
            response_format={ "type": "json_object" }
        )
        return json.loads(response.choices[0].message.content.strip())
    except Exception as e:
        return merged_analysis


def invoke_chain_of_thought(entries):
    """
    Process news entries using a chain of GPT analyses.
    
    Args:
        entries (list): List of dictionaries containing news entries
    Returns:
        list: List of analyzed entries with their evaluations
    """
    analyzed_entries = []
    # import pdb; pdb.set_trace()
    
    for entry in entries:
        
        try:
            # Step 1: Identify companies and tickers
            companies_tickers = determine_direct_ticker_companies_mentioned(
                entry['title'], 
                entry['summary']
            )

            print(f"companies_tickers: {companies_tickers}")
            
            # Step 2: Generate questions
            questions = invoke_question_prompter(
                entry['title'], 
                entry['summary'], 
                companies_tickers
            )

            print(f"questions: {questions}")
            
            # Step 3: Get answers for each question
            all_answers = []
            entry["question_and_answers"] = []
            for question in questions:
                answer = invoke_answer_worker(
                    question,
                    entry['title'],
                    entry['summary'],
                    companies_tickers
                )
                all_answers.append(answer)
                print(f'answer: {answer["tickers"]}')
                entry["question_and_answers"].append({"question": question["question"], "answer": answer["tickers"]})
                print(f'Error not in append entry!')
            
            print("Here loop done!")
            # Merge all answers
            # merged_analysis = []

            # processed_tickers = set()
            # for analysis in merged_analysis:
            #     if analysis["ticker"] not in processed_tickers:
            #         processed_tickers.add(analysis["ticker"])
            #         merged_analysis.append(analysis)


            # print(f"merged_analysis: {merged_analysis}")
            
            # Step 4: Final evaluation
            # final_evaluation = invoke_evaluation_judge(
            #     merged_analysis,
            #     entry['title'],
            #     entry['summary']
            # )

            # print(f"final_evaluation: {final_evaluation}")
            print("Here!")
            
            # Combine all analysis into a single result
            analyzed_entry = {
                "title": entry['title'],
                "summary": entry['summary'],
                "source": entry['source'],
                "companies_tickers": companies_tickers,
                "question_and_answers": entry["question_and_answers"],
                "questions": questions,
                # "merged_analysis": merged_analysis,
                # "final_evaluation": final_evaluation
            }
            print(f'Error not in assignment of analyzed_entry!')
            
            analyzed_entries.append(analyzed_entry)
            
        except Exception as e:
            print(f"Error analyzing entry {entry['title']}: {str(e)}")
            continue
    
    return analyzed_entries

test_entries = [
    {'title': 'Vanguard\'s Record Fee CutPuts Rivals BlackRock, Invesco in Tough Spot', 'title_detail': {'type': 'text/plain', 'language': None, 'base': 'https://feeds.bloomberg.com/markets/news.rss', 'value': 'Vanguard\'s Record Fee CutPuts Rivals BlackRock, Invesco in Tough Spot'}, 'summary': 'Vanguard Group Inc.\'s biggest salvo yet in its campaign to cut fees for the investing masses presents industry rivals with a painful choice. Follow suit and lose potentially hundreds of millions in revenue &mdash; or hold the line and risk losing badly needed market share.', 'summary_detail': {'type': 'text/html', 'language': None, 'base': 'https://feeds.bloomberg.com/markets/news.rss', 'value': 'Vanguard Group Inc.\'s biggest salvo yet in its campaign to cut fees for the investing masses presents industry rivals with a painful choice. Follow suit and lose potentially hundreds of millions in revenue &mdash; or hold the line and risk losing badly needed market share.'}, 'links': [{'rel': 'alternate', 'type': 'text/html', 'href': 'https://www.bloomberg.com/news/articles/2025-02-05/vanguard-s-record-fee-cuts-tighten-screws-on-blackrock-invesco'}], 'link': 'https://www.bloomberg.com/news/articles/2025-02-05/vanguard-s-record-fee-cuts-tighten-screws-on-blackrock-invesco', 'id': 'https://www.bloomberg.com/news/articles/2025-02-05/vanguard-s-record-fee-cuts-tighten-screws-on-blackrock-invesco', 'guidislink': False, 'authors': [{'name': 'Katie Greifeld, Vildana Hajric'}], 'author': 'Katie Greifeld, Vildana Hajric', 'author_detail': {'name': 'Katie Greifeld, Vildana Hajric'}, 'published': 'Wed, 05 Feb 2025 14:46:46 GMT', 'tags': [{'term': 'NYS:IVZ', 'scheme': 'stock-symbol', 'label': None}, {'term': 'NYS:BLK', 'scheme': 'stock-symbol', 'label': None}], 'media_content': [{'url': 'https://assets.bwbx.io/images/users/iqjWHBFdfxIU/igTb3jvPuPtw/v1/1200x-1.jpg', 'type': 'image/jpeg'}], 'media_thumbnail': [{'url': 'https://assets.bwbx.io/images/users/iqjWHBFdfxIU/igTb3jvPuPtw/v1/1200x-1.jpg'}], 'href': '', 'content': [{'type': 'text/plain', 'language': None, 'base': 'https://feeds.bloomberg.com/markets/news.rss', 'value': 'A history of consistent cost cutting has created a sense of goodwill and loyalty among Vanguard\'s client base.'}]},
{'title': 'Poland Re-enters Regional FX Debt Rush With Dollar Bond Offer', 'title_detail': {'type': 'text/plain', 'language': None, 'base': 'https://feeds.bloomberg.com/markets/news.rss', 'value': 'Poland Re-enters Regional FX Debt Rush With Dollar Bond Offer'}, 'summary': 'Poland is returning to international markets for a second time in as many months, selling dollar-denominated bonds as part of efforts to cover record financing needs.', 'summary_detail': {'type': 'text/html', 'language': None, 'base': 'https://feeds.bloomberg.com/markets/news.rss', 'value': 'Poland is returning to international markets for a second time in as many months, selling dollar-denominated bonds as part of efforts to cover record financing needs.'}, 'links': [{'rel': 'alternate', 'type': 'text/html', 'href': 'https://www.bloomberg.com/news/articles/2025-02-05/poland-re-enters-regional-fx-debt-rush-with-dollar-bond-offer'}], 'link': 'https://www.bloomberg.com/news/articles/2025-02-05/poland-re-enters-regional-fx-debt-rush-with-dollar-bond-offer', 'id': 'https://www.bloomberg.com/news/articles/2025-02-05/poland-re-enters-regional-fx-debt-rush-with-dollar-bond-offer', 'guidislink': False, 'authors': [{'name': 'Agnieszka Barteczko, Kevin Kingsbury'}], 'author': 'Agnieszka Barteczko, Kevin Kingsbury', 'author_detail': {'name': 'Agnieszka Barteczko, Kevin Kingsbury'}, 'published': 'Wed, 05 Feb 2025 14:43:45 GMT', 'media_content': [{'url': 'https://assets.bwbx.io/images/users/iqjWHBFdfxIU/iq7Jau_xHBVg/v0/1200x-1.jpg', 'type': 'image/jpeg'}], 'media_thumbnail': [{'url': 'https://assets.bwbx.io/images/users/iqjWHBFdfxIU/iq7Jau_xHBVg/v0/1200x-1.jpg'}], 'href': '', 'content': [{'type': 'text/plain', 'language': None, 'base': 'https://feeds.bloomberg.com/markets/news.rss', 'value': 'The Ministry of Finance, Warsaw. Source: picture alliance/Getty Images'}]},
]


def store_analyzed_entries_in_db(analyzed_entries):
    """
    Store the analyzed entries in MongoDB.
    
    Args:
        analyzed_entries (list): List of dictionaries containing analyzed news entries
    """
    print(f"inside store_analyzed_entries_in_db")
    for entry in analyzed_entries:
        # Create a unique identifier based on title and summary
        unique_id = f"{entry['title']}_{entry['summary']}"
        entry["id"] = unique_id
        
        # Add timestamp for when this was stored
        entry['stored_at'] = time.time()
        
        # Store in MongoDB, using upsert to avoid duplicates
        mongo_adapter.load_items_into_collection(
            "news-headlines",
            items=[entry]
        )
        print("Inserted doc!")


def format_analyzed_entries_for_email(analyzed_entries):
    """
    Format analyzed entries into a readable string for email.
    
    Args:
        analyzed_entries (list): List of dictionaries containing analyzed news entries
    Returns:
        str: Formatted string containing the analysis
    """
    formatted_text = []
    
    for entry in analyzed_entries:
        # Add headline section
        formatted_text.append(f"📰 HEADLINE: {entry['title']}\n")
        formatted_text.append(f"📝 SUMMARY: {entry['summary']}\n")
        
        # Add companies and tickers mentioned
        if entry.get('companies_tickers'):
            tickers = entry['companies_tickers'].get('tickers_mentioned', [])
            companies = entry['companies_tickers'].get('companies_mentioned', [])
            if tickers:
                formatted_text.append(f"🎯 TICKERS MENTIONED: {', '.join(tickers)}")
            if companies:
                formatted_text.append(f"🏢 COMPANIES MENTIONED: {', '.join(companies)}")
            formatted_text.append("")
        
        # Add questions and answers
        if entry.get('question_and_answers'):
            formatted_text.append("❓ ANALYSIS QUESTIONS & ANSWERS:")
            for qa in entry['question_and_answers']:
                formatted_text.append(f"\nQ: {qa['question']}")
                formatted_text.append("A: ")
                for ticker_info in qa['answer']:
                    formatted_text.append(f"   • {ticker_info['symbol']}: {ticker_info['reasoning']}")
            formatted_text.append("")
        
        formatted_text.append("=" * 80 + "\n")
    
    return "\n".join(formatted_text)


def parse_rss_feeds():
    """
    Continuously parse RSS feeds from the URLS dictionary every second
    and convert them to JSON format using Pydantic models.
    """
    # Set to store processed entries (title + summary pairs)
    processed_entries = set()
    
    while True:
        all_analyzed_entries = []
        for source, urls in URLS.items():
            response_object = SOURCE_TO_RESPONSE_OBJECT_MAP[source]
            for url in urls:
                try:
                    # Parse the RSS feed
                    feed = feedparser.parse(url)
                    
                    # Convert feed entries to Pydantic objects
                    entries = []
                    for entry in feed.entries: #feed.entries[:10]:
                        # Create a unique identifier for this entry
                        entry_id = (entry.get('title', ''), entry.get('summary', ''))
                        
                        # Only process if we haven't seen this entry before
                        if entry_id not in processed_entries:
                            # Create a Pydantic model instance
                            entry_data = response_object.from_feed_entry(entry, url)
                            if not entry_data:
                                continue

                            entries.append(entry_data.model_dump())  # Convert to dict for further processing
                            processed_entries.add(entry_id)
                    
                    if entries:  # Only print if we have new entries
                        # Get detailed analysis
                        analyzed_entries = invoke_chain_of_thought(entries)
                        print(f"\nFound and analyzed {len(entries)} new entries from {source}: {url}")
                        
                        # Store the analyzed entries in MongoDB
                        # store_analyzed_entries_in_db(analyzed_entries)
                        # import pdb; pdb.set_trace()

                        if len(analyzed_entries) == 0:
                            continue
                        
                        formatted_entries = format_analyzed_entries_for_email(analyzed_entries)
                        all_analyzed_entries.append(f"[SOURCE = {source}] {formatted_entries}")
                    
                except Exception as e:
                    print(f"Error parsing {source} feed {url}: {str(e)}")
        
        if len(all_analyzed_entries) > 0:
            send_email(subject=f"Processed headlines batch: {datetime.now()}", body="\n".join(all_analyzed_entries))
            time.sleep(10)

if __name__ == "__main__":
    parse_rss_feeds()





