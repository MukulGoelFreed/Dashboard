import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from datetime import datetime, timedelta
import numpy as np
import base64

# --- Page Configuration ---
st.set_page_config(
    page_title="Advanced MoEngage Dashboard",
    page_icon="🚀",
    layout="wide"
)

# --- DATA FETCHING & PROCESSING ---

@st.cache_data(ttl=600)
def fetch_campaign_data(start_date, end_date):
    """
    Fetches Campaign Stats data from the MoEngage Stats API.
    
    Corrects the API endpoint, payload structure, and authentication
    based on the MoEngage Stats API documentation.
    """
    creds = st.secrets["moengage"]
    
    # The requests library handles Base64 encoding for you with the auth parameter.
    username = creds['data_api_id']
    password = creds['data_api_key']
    
    # request set up for headers as per documentation.
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "MOE-APPKEY": creds['app_id']
    }
    
    # Note: start_date and end_date are in YYYY-MM-DD format, not with Z.
    payload = {
        "request_id": "streamlit-dashboard-request-" + datetime.now().isoformat(),
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "attribution_type": "CLICK_THROUGH", # Can be changed via a Streamlit filter if needed
        "metric_type": "TOTAL" # Or "UNIQUE"
    }

    try:
        response = requests.post(
            creds['api_base_url'], 
            headers=headers, 
            json=payload, 
            auth=(username, password)
        )
        response.raise_for_status()
        data = response.json()
        
        # The API returns a dictionary with campaign IDs as keys.
        campaigns = []
        if 'data' in data:
            for campaign_id, campaign_data in data['data'].items():
                # Extract relevant stats from the nested JSON structure
                if campaign_data and len(campaign_data) > 0 and 'platforms' in campaign_data[0]:
                    platform_data = campaign_data[0]['platforms']
                    # Assuming we want to aggregate all platform data for a campaign
                    all_platforms = next(iter(platform_data.values()))
                    stats = all_platforms.get('locales', {}).get('all_locales', {}).get('variations', {}).get('all_variations', {}).get('performance_stats', {})
                    
                    campaign_entry = {
                        'campaign_id': campaign_id,
                        'name': 'Campaign ' + campaign_id, # The API doesn't return the name, so we use a placeholder.
                        'stats': stats
                    }
                    campaigns.append(campaign_entry)
        
        return campaigns
    
    except requests.exceptions.RequestException as e:
        st.error(f"API Error: {e}")
        return []

def get_mock_flow_data():
    """Returns mock data for Flows, as this requires the complex Data Exports API."""
    data = [
        {'name': 'New User Onboarding Flow', 'entered': 1500, 'completed': 1100, 'dropped_off': 400, 'conversions': 850, 'created_by': 'marketing@example.com', 'status': 'Active'},
        {'name': 'Cart Abandonment Recovery', 'entered': 800, 'completed': 500, 'dropped_off': 300, 'conversions': 450, 'created_by': 'retention@example.com', 'status': 'Active'},
        {'name': 'Subscription Renewal Reminder', 'entered': 2500, 'completed': 2200, 'dropped_off': 300, 'conversions': 2000, 'created_by': 'marketing@example.com', 'status': 'Finished'},
    ]
    return pd.DataFrame(data)

def calculate_metrics(df, mode='campaign'):
    """Calculates all possible metrics from the base data."""
    if df.empty:
        return df

    if mode == 'campaign':
        # API metric names are different from original code, so map them
        df = df.rename(columns={
            'name': 'Campaign Name', 
            'stats.sent': 'Sent', 
            'stats.delivered': 'Delivered', 
            'stats.impression': 'Opens/Views', # Changed to impression as per API
            'stats.click': 'Clicks', 
            'stats.conversion': 'Conversions', # Changed to conversion as per API
            'stats.failed': 'Failed'
        })
        
        df['Delivery Rate (%)'] = (df['Delivered'] / df['Sent']).replace([np.inf, -np.inf], 0).fillna(0) * 100
        df['Open Rate (%)'] = (df['Opens/Views'] / df['Delivered']).replace([np.inf, -np.inf], 0).fillna(0) * 100
        df['CTR (%)'] = (df['Clicks'] / df['Opens/Views']).replace([np.inf, -np.inf], 0).fillna(0) * 100 # CTR is clicks/impressions
        df['CTOR (%)'] = (df['Clicks'] / df['Opens/Views']).replace([np.inf, -np.inf], 0).fillna(0) * 100
        df['CTC Rate (%)'] = (df['Conversions'] / df['Clicks']).replace([np.inf, -np.inf], 0).fillna(0) * 100

    elif mode == 'flow':
        df['Completion Rate (%)'] = (df['completed'] / df['entered']) * 100
        df['Conversion Rate (%)'] = (df['conversions'] / df['entered']) * 100

    return df.round(2)

# --- UI LAYOUT ---
st.title("🚀 Advanced MoEngage Performance Dashboard")

# --- SIDEBAR FILTERS ---
st.sidebar.header("Dashboard Controls")
dashboard_mode = st.sidebar.radio("Select Dashboard Mode", ['Track Individual Campaigns', 'Track Flows'])

# Common Filters
st.sidebar.subheader("Filters")
date_range = st.sidebar.date_input("Select Date Range", (datetime.now() - timedelta(days=7), datetime.now() - timedelta(days=1)))

# --- MAIN DASHBOARD AREA ---
if dashboard_mode == 'Track Individual Campaigns':
    # Fetch and process data
    with st.spinner("Fetching campaign data from MoEngage..."):
        # The fetch_campaign_data function no longer accepts the 'filters' parameter
        raw_data = fetch_campaign_data(date_range[0], date_range[1])
        df = pd.DataFrame(raw_data)
        if not df.empty:
            df = pd.concat([df.drop(['stats'], axis=1), pd.json_normalize(df['stats'])], axis=1)
        
    df_processed = calculate_metrics(df, mode='campaign')

    if df_processed.empty:
        st.warning("No campaign data found for the selected date range.")
    else:
        # KPI Summary
        st.header("KPI Summary")
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("Total Campaigns", f"{len(df_processed):,}")
        kpi2.metric("Total Delivered", f"{df_processed['Delivered'].sum():,}")
        kpi3.metric("Total Clicks", f"{df_processed['Clicks'].sum():,}")
        kpi4.metric("Total Conversions", f"{df_processed['Conversions'].sum():,}")

        # Top and Worst Performers
        st.header("Campaign Performance Analysis")
        sort_by = st.selectbox("Analyze performance by:", ['Conversions', 'Clicks', 'CTR (%)', 'CTC Rate (%)'])
        
        top_10 = df_processed.nlargest(10, sort_by)
        worst_10 = df_processed.nsmallest(10, sort_by)

        col1, col2 = st.columns(2)
        with col1:
            st.subheader(f"🏆 Top 10 Performing Campaigns by {sort_by}")
            st.dataframe(top_10[['Campaign Name', sort_by]])
        with col2:
            st.subheader(f"📉 Worst 10 Performing Campaigns by {sort_by}")
            st.dataframe(worst_10[['Campaign Name', sort_by]])

        # Detailed Data Table
        st.header("Detailed Campaign Report")
        st.dataframe(df_processed)

elif dashboard_mode == 'Track Flows':
    st.info("Displaying mock data. A production version of this view requires the MoEngage Data Exports API.")
    
    # Flow-specific filters
    flow_name_filter = st.sidebar.selectbox("Flow Name", ['All Flows', 'New User Onboarding Flow', 'Cart Abandonment Recovery'])
    
    df_flows = get_mock_flow_data()
    df_processed = calculate_metrics(df_flows, mode='flow')
    
    # Filter based on selection
    if flow_name_filter != 'All Flows':
        df_processed = df_processed[df_processed['name'] == flow_name_filter]

    # Display Flow KPIs and Data
    st.header("Flows Performance Summary")
    kpi1, kpi2, kpi3 = st.columns(3)
    kpi1.metric("Total Users Entered", f"{df_processed['entered'].sum():,}")
    kpi2.metric("Total Users Completed", f"{df_processed['completed'].sum():,}")
    kpi3.metric("Total Conversions", f"{df_processed['conversions'].sum():,}")
    
    st.header("Detailed Flow Report")
    st.dataframe(df_processed)
