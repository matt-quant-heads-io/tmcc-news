import streamlit as st
import time
import os
from mongo_adapter import MongoAdapter
from datetime import datetime
import pandas as pd
import json
from bson import ObjectId
import math
import networkx as nx
import matplotlib.pyplot as plt
import io
from PIL import Image


def save_and_display_visualization(analysis, container):
    """
    Create and save a networkx visualization, then display it in the given container.
    
    Args:
        analysis (dict): Dictionary containing analysis results
        container: Streamlit container to display the visualization
    """
    # Create a directed graph
    G = nx.DiGraph()
    
    # Create a root node with title and subject (orange)
    title = str(analysis.get('title', ''))
    companies = analysis.get('companies_tickers', {}).get('companies_mentioned', [])
    companies_str = ', '.join(companies) if companies else 'No companies mentioned'
    root_text = f"{title}\n{companies_str}"
    G.add_node(root_text, pos=(0, 0), color='orange')  # Root at left middle
    
    # Get questions and answers
    qa_pairs = analysis.get('question_and_answers', [])
    
    # Calculate layout positions
    num_questions = len(qa_pairs)
    vertical_spacing = 4.0  # Increased vertical spacing between question nodes
    
    # Add question nodes (blue) and their answer nodes (light purple)
    for i, qa in enumerate(qa_pairs):
        # Calculate y position to center questions vertically
        y_pos = ((num_questions - 1) / 2 - i) * vertical_spacing
        
        # Add question node (blue)
        question = str(qa.get('question', {}))
        # Keep the full question text intact for the blue node
        G.add_node(question, pos=(2, y_pos), color='lightblue')
        G.add_edge(root_text, question)
        
        # Add answer nodes (light purple) for this question
        answers = qa.get('answer', [])
        num_answers = len(answers)
        for j, answer in enumerate(answers):
            # Calculate position for answer nodes with more spacing
            answer_y = y_pos + (j - (num_answers - 1) / 2) * (vertical_spacing / 3)
            
            # Create answer node text with ticker and reasoning
            ticker = str(answer.get('symbol', ''))
            reasoning = str(answer.get('reasoning', ''))
            answer_text = f"{ticker}\n{reasoning}"
            
            G.add_node(answer_text, pos=(4, answer_y), color='plum')
            G.add_edge(question, answer_text)
    
    # Get node positions and colors
    pos = nx.get_node_attributes(G, 'pos')
    colors = [G.nodes[node]['color'] for node in G.nodes()]
    
    # Create new figure with larger size for better readability
    plt.figure(figsize=(20, 15))
    
    # Draw the graph with adjusted parameters for better readability
    nx.draw(G, pos,
            node_color=colors,
            node_size=8000,  # Increased node size
            font_size=7,     # Slightly smaller font to fit more text
            font_weight='bold',
            arrows=True,
            edge_color='gray',
            width=2,
            arrowsize=20,
            with_labels=True,
            bbox=dict(facecolor='white', edgecolor='none', alpha=0.7))  # Add white background to text
    
    # Adjust layout to prevent text cutoff
    plt.margins(0.2)
    
    # Save the plot to a bytes buffer
    buf = io.BytesIO()
    plt.savefig(buf, format='jpg', bbox_inches='tight', dpi=300)
    buf.seek(0)
    plt.close()
    
    # Display the image in the container
    image = Image.open(buf)
    container.image(image, use_column_width=True)
    
    # Get node positions and colors
    pos = nx.get_node_attributes(G, 'pos')
    colors = [G.nodes[node]['color'] for node in G.nodes()]
    
    # Create new figure with larger size
    plt.figure(figsize=(15, 10))
    
    # Draw the graph
    nx.draw(G, pos,
            with_labels=True,
            node_color=colors,
            node_size=4000,
            font_size=8,
            font_weight='bold',
            arrows=True,
            edge_color='gray',
            width=2,
            arrowsize=20)
    
    # Adjust layout
    plt.title(f"Analysis Visualization: {analysis['title'][:50]}...")
    plt.tight_layout()
    
    # Save the plot to a bytes buffer
    buf = io.BytesIO()
    plt.savefig(buf, format='jpg', bbox_inches='tight')
    buf.seek(0)
    plt.close()
    
    # Display the image in the container
    image = Image.open(buf)
    container.image(image, use_column_width=True)

# Custom JSON encoder to handle ObjectId
class MongoJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        return super().default(obj)

# Initialize MongoDB connection
@st.cache_resource
def init_mongo():
    mongo_adapter = MongoAdapter(
        connection_string="mongodb://localhost:27017",
        database_name="tmcc-news"
    )
    return mongo_adapter

# Function to fetch headlines with pagination
def fetch_headlines(mongo_adapter, query=None, page=1, per_page=25):
    # Calculate skip value
    skip = (page - 1) * per_page
    
    # First get the total count
    cursor = mongo_adapter.read_from_collection("news-headlines", **(query if query else {}))
    total_count = len(list(cursor))
    
    # Then fetch the paginated results
    cursor = mongo_adapter.read_from_collection("news-headlines", **(query if query else {}))
    paginated_results = list(cursor)[skip:skip + per_page]
    
    return paginated_results, total_count

# Function to display JSON-like structure
def display_json_structure(headline):
    # Create expandable container for each headline
    with st.expander(f"📰 {headline.get('title', 'No Title')}", expanded=True):
        # Format the headline data
        json_data = {
            "_id": {
                "$oid": headline.get('_id', '')
            },
            "title": headline.get('title', ''),
            "summary": headline.get('summary', ''),
            "source": headline.get('source', ''),
            "companies_tickers": {
                "tickers_mentioned": headline.get('companies_tickers', {}).get('tickers_mentioned', []),
                "companies_mentioned": headline.get('companies_tickers', {}).get('companies_mentioned', [])
            },
            "question_and_answers": headline.get('question_and_answers', []),
            "questions": headline.get('questions', []),
            "id": headline.get('id', ''),
            "stored_at": headline.get('stored_at', 0)
        }

        # Display full-width JSON
        st.code(json.dumps(json_data, indent=2, cls=MongoJSONEncoder), language='json')
        
        # Create a horizontal layout for buttons using columns
        cols = st.columns(6)  # Create 6 equal columns for the buttons
        
        # Place each button in its own column
        with cols[0]:
            if st.button("✏️", key=f"edit_{str(headline.get('_id'))}", help="Edit"):
                pass
        with cols[1]:
            if st.button("📋", key=f"copy_{str(headline.get('_id'))}", help="Copy"):
                pass
        with cols[2]:
            if st.button("💬", key=f"comment_{str(headline.get('_id'))}", help="Comment"):
                pass
        with cols[3]:
            if st.button("🗑️", key=f"delete_{str(headline.get('_id'))}", help="Delete"):
                pass
        with cols[4]:
            if st.button("📊", key=f"viz_{str(headline.get('_id'))}", help="Visualize"):
                # Create visualization below the JSON and buttons
                viz_container = st.container()
                save_and_display_visualization(json_data, viz_container)
        
       

# Query examples
QUERY_EXAMPLES = '''// Case-insensitive search for "Vanguard" in title
{"title": {"$regex": "Vanguard", "$options": "i"}}

// Find articles from a specific source
{"source": "https://feeds.bloomberg.com/markets/news.rss"}

// Find articles with specific tickers
{"companies_tickers.tickers_mentioned": {"$in": ["AAPL", "GOOGL"]}}

// Complex query with multiple conditions
{
    "$and": [
        {"title": {"$regex": "market", "$options": "i"}},
        {"stored_at": {"$gte": 1738790075}}
    ]
}'''

def main():
    # Main app
    st.title('📰 Financial News Headlines')
    st.write('Auto-refreshing news headlines from various financial sources')

    # Initialize MongoDB connection
    mongo = init_mongo()

    # Initialize session state for pagination if not exists
    if 'page' not in st.session_state:
        st.session_state.page = 1

    # Add search functionality
    search_col1, search_col2, search_col3 = st.columns([0.7, 0.15, 0.15])
    with search_col1:
        search_query = st.text_area("Enter MongoDB query (JSON):", height=100)
    with search_col2:
        search_button = st.button("Search", key="search_button")
    with search_col3:
        info_button = st.button("ℹ️ Query Examples", key="info_button")

    # Show query examples if info button is clicked
    if info_button:
        with st.expander("Query Examples", expanded=True):
            st.code(QUERY_EXAMPLES, language='javascript')

    # Parse search query
    query_dict = None
    if search_query.strip():
        try:
            query_dict = json.loads(search_query)
            st.success("Valid MongoDB query")
        except json.JSONDecodeError:
            st.error("Invalid JSON format")

    # Reset page when new search is performed
    if search_button:
        st.session_state.page = 1

    # Add a placeholder for the data
    data_placeholder = st.empty()

    # Fetch headlines with pagination
    headlines, total_count = fetch_headlines(mongo, query_dict, st.session_state.page)
    total_pages = math.ceil(total_count / 25)

    with data_placeholder.container():
        # Display last update time and pagination info
        col1, col2 = st.columns([0.7, 0.3])
        with col1:
            st.write(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        with col2:
            st.write(f"Page {st.session_state.page} of {total_pages} (Total items: {total_count})")
        
        # Display headlines in JSON format
        if headlines:
            for headline in headlines:
                display_json_structure(headline)
        else:
            st.warning("No headlines found")
        
        # Pagination controls
        if total_pages > 1:
            col1, col2, col3 = st.columns([1, 2, 1])
            with col1:
                if st.session_state.page > 1:
                    if st.button("← Previous"):
                        st.session_state.page -= 1
                        st.experimental_rerun()
            
            with col2:
                # Page number selector
                page_numbers = list(range(1, total_pages + 1))
                selected_page = st.selectbox(
                    "Go to page",
                    page_numbers,
                    index=st.session_state.page - 1,
                    key="page_selector"
                )
                if selected_page != st.session_state.page:
                    st.session_state.page = selected_page
                    st.experimental_rerun()
            
            with col3:
                if st.session_state.page < total_pages:
                    if st.button("Next →"):
                        st.session_state.page += 1
                        st.experimental_rerun()

        # Wait for 2 minutes before refreshing
        time.sleep(120)

if __name__ == "__main__":
    main()