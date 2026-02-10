"""
Google Maps Review Scraper - Streamlit Frontend

A web interface for enriching business leads with Google Maps reviews,
website data, social links, and AI-generated personalized emails.
"""

import streamlit as st
import pandas as pd
from io import BytesIO
import os
import scraper_adapter as adapter

# Page config
st.set_page_config(
    page_title="Google Maps Lead Enricher",
    page_icon="🗺️",
    layout="wide"
)

# Constants
PREVIEW_SIZE = 10

# Initialize session state
if 'df' not in st.session_state:
    st.session_state.df = None
if 'results_ready' not in st.session_state:
    st.session_state.results_ready = False


def df_to_csv_download(df, filename="leads.csv"):
    """Convert DataFrame to CSV download link."""
    csv_buffer = BytesIO()
    df.to_csv(csv_buffer, index=False)
    csv_buffer.seek(0)
    return csv_buffer.getvalue()


def validate_inputs(require_google_key=False, require_email_config=False):
    """Validate required inputs before running."""
    errors = []

    if require_google_key and not st.session_state.get('google_api_key', '').strip():
        errors.append("Google Maps API key is required")

    if require_email_config and st.session_state.get('enrich_emails', False):
        if not st.session_state.get('llm_provider', ''):
            errors.append("LLM provider is required for email generation")
        if not st.session_state.get('llm_model', '').strip():
            errors.append("LLM model is required for email generation")
        if not st.session_state.get('llm_api_key', '').strip():
            errors.append("LLM API key is required for email generation")
        if not st.session_state.get('product_description', '').strip():
            errors.append("Product description is required for email generation")

    return errors


# ========== SIDEBAR ==========
with st.sidebar:
    st.title("🗺️ Lead Enricher")
    st.markdown("---")

    st.subheader("🔑 API Keys")

    # Help expander for Google Maps API
    with st.expander("ℹ️ How to get a Google Maps API key"):
        st.markdown("""
        **Follow these steps:**

        1. Go to [Google Cloud Console](https://console.cloud.google.com)
        2. Create a new project (or select existing)
        3. Enable the **Places API (New)**
        4. Go to **Credentials** → **Create Credentials** → **API Key**
        5. Copy your API key and paste below

        **Pricing:**
        - $200 free credit/month from Google
        - Each search costs ~$0.02

        [📖 Detailed Guide](https://developers.google.com/maps/documentation/places/web-service/get-api-key)
        """)

    # Google Maps API Key (with optional env var fallback)
    default_google_key = st.session_state.get('google_api_key', '') or os.getenv('GOOGLE_MAPS_API_KEY', '')
    google_api_key = st.text_input(
        "Google Maps API Key",
        value=default_google_key,
        type="password",
        key="google_api_key",
        help="Required for all operations"
    )

    st.markdown("---")
    st.subheader("✨ Enrichment Options")

    # Enrichment checkboxes
    enrich_reviews = st.checkbox(
        "Google Reviews",
        value=True,
        help="Add Google rating and review count"
    )

    enrich_website = st.checkbox(
        "Website & Social Links",
        value=False,
        help="Extract LinkedIn, Facebook, Instagram, Twitter + research brief"
    )

    enrich_emails = st.checkbox(
        "AI Generated Emails",
        value=False,
        key="enrich_emails",
        help="Generate personalized cold outreach emails"
    )

    # LLM Configuration (shown only if email generation is enabled)
    if enrich_emails:
        st.markdown("---")
        st.subheader("🤖 LLM Configuration")

        # Help expander for LLM API keys
        with st.expander("ℹ️ How to get LLM API keys"):
            st.markdown("""
            **OpenAI** (Recommended for beginners)
            - Go to [platform.openai.com](https://platform.openai.com)
            - Sign up → API Keys → Create new key
            - Model: `gpt-4o-mini` (cheap) or `gpt-4o` (best)
            - Cost: ~$0.10 per 100 emails with gpt-4o-mini

            **Anthropic**
            - Go to [console.anthropic.com](https://console.anthropic.com)
            - Get API key → Copy
            - Model: `claude-sonnet-4-5-20250929`

            **Free Options:**
            - OpenRouter: Some free models available at [openrouter.ai](https://openrouter.ai)
            """)

        llm_provider = st.selectbox(
            "LLM Provider",
            options=["", "openai", "anthropic", "gemini", "openrouter", "perplexity"],
            key="llm_provider",
            help="Choose your AI provider"
        )

        llm_model = st.text_input(
            "Model Name",
            key="llm_model",
            placeholder="e.g., gpt-4o-mini, claude-sonnet-4-5-20250929",
            help="Specific model to use"
        )

        default_llm_key = st.session_state.get('llm_api_key', '') or os.getenv(f'{llm_provider.upper()}_API_KEY', '') if llm_provider else ''
        llm_api_key = st.text_input(
            "LLM API Key",
            value=default_llm_key,
            type="password",
            key="llm_api_key"
        )

        product_description = st.text_area(
            "Your Product/Service",
            key="product_description",
            placeholder="Describe what you're offering...",
            help="Used to personalize each email"
        )


# ========== MAIN CONTENT ==========
st.title("Google Maps Lead Enricher")
st.markdown("Find businesses on Google Maps and enrich them with reviews, social links, and AI-generated emails")

# Create tabs
tab1, tab2 = st.tabs(["🔍 Search Google Maps", "📁 Upload CSV"])

# ========== TAB 1: SEARCH MODE ==========
with tab1:
    st.subheader("Search for Businesses")

    col1, col2 = st.columns([3, 1])

    with col1:
        search_query = st.text_input(
            "Search Query",
            placeholder="e.g., dentists in Austin TX",
            key="search_query"
        )

    with col2:
        max_results = st.number_input(
            "Max Results",
            min_value=1,
            max_value=100,
            value=20,
            key="max_results"
        )

    col_preview, col_run = st.columns(2)

    with col_preview:
        if st.button("🔍 Preview First 10", key="preview_search", use_container_width=True):
            errors = validate_inputs(require_google_key=True, require_email_config=False)
            if errors:
                for error in errors:
                    st.error(error)
            elif not search_query.strip():
                st.error("Please enter a search query")
            else:
                with st.spinner("Searching..."):
                    try:
                        # Create scraper
                        scraper = adapter.create_scraper(google_api_key)

                        # Search (limited to preview size)
                        df = adapter.search_places(scraper, search_query, min(PREVIEW_SIZE, max_results))

                        if df.empty:
                            st.warning("No results found")
                        else:
                            st.session_state.df = df
                            st.session_state.results_ready = False
                            st.success(f"Found {len(df)} results (preview mode)")

                    except Exception as e:
                        st.error(f"Error: {str(e)}")

    with col_run:
        if st.button("▶️ Run Full Enrichment", key="run_search", type="primary", use_container_width=True):
            errors = validate_inputs(require_google_key=True, require_email_config=True)
            if errors:
                for error in errors:
                    st.error(error)
            elif not search_query.strip():
                st.error("Please enter a search query")
            else:
                try:
                    # Create scraper
                    scraper = adapter.create_scraper(google_api_key)

                    # Step 1: Search
                    with st.status("🔍 Searching Google Maps...", expanded=True) as status:
                        st.write(f"Query: {search_query}")
                        df = adapter.search_places(scraper, search_query, max_results)

                        if df.empty:
                            status.update(label="No results found", state="error")
                            st.stop()

                        st.write(f"✓ Found {len(df)} results")
                        status.update(label=f"✓ Search complete: {len(df)} results", state="complete")

                    # Step 2: Google Reviews (if enabled)
                    if enrich_reviews:
                        with st.status("⭐ Enriching with Google reviews...", expanded=True) as status:
                            progress_bar = st.progress(0)

                            def update_progress(current, total):
                                progress_bar.progress(current / total)
                                st.write(f"Processing: {current}/{total}")

                            df = adapter.enrich_with_reviews(scraper, df, update_progress)
                            status.update(label="✓ Google reviews added", state="complete")

                    # Step 3: Website & Social (if enabled)
                    if enrich_website:
                        with st.status("🌐 Enriching with website data...", expanded=True) as status:
                            progress_bar = st.progress(0)

                            def update_progress(current, total):
                                progress_bar.progress(current / total)
                                st.write(f"Processing: {current}/{total}")

                            df = adapter.enrich_with_website_data(df, update_progress)
                            status.update(label="✓ Website data added", state="complete")

                    # Step 4: AI Emails (if enabled)
                    if enrich_emails:
                        with st.status("✉️ Generating personalized emails...", expanded=True) as status:
                            progress_bar = st.progress(0)

                            def update_progress(current, total):
                                progress_bar.progress(current / total)
                                st.write(f"Processing: {current}/{total}")

                            # Create email generator
                            generator = adapter.create_email_generator(
                                llm_model,
                                llm_api_key,
                                adapter.DEFAULT_PROMPT_TEMPLATE
                            )

                            df = adapter.generate_emails(
                                df,
                                generator,
                                product_description,
                                update_progress
                            )
                            status.update(label="✓ Emails generated", state="complete")

                    # Save to session state
                    st.session_state.df = df
                    st.session_state.results_ready = True
                    st.success(f"✅ Enrichment complete! {len(df)} leads ready")

                except Exception as e:
                    st.error(f"Error: {str(e)}")
                    import traceback
                    st.code(traceback.format_exc())

# ========== TAB 2: UPLOAD CSV ==========
with tab2:
    st.subheader("Upload Existing CSV")

    uploaded_file = st.file_uploader(
        "Choose a CSV file",
        type=['csv'],
        help="Upload a CSV with Company Name and Company Address columns"
    )

    if uploaded_file is not None:
        try:
            df_upload = pd.read_csv(uploaded_file)
            st.write(f"**Loaded:** {len(df_upload)} rows, {len(df_upload.columns)} columns")
            st.dataframe(df_upload.head(), use_container_width=True)

            col_preview, col_run = st.columns(2)

            with col_preview:
                if st.button("🔍 Preview First 10", key="preview_upload", use_container_width=True):
                    errors = validate_inputs(require_google_key=False, require_email_config=False)
                    if errors:
                        for error in errors:
                            st.error(error)
                    else:
                        # Just show first 10 rows without processing
                        st.session_state.df = df_upload.head(PREVIEW_SIZE).copy()
                        st.session_state.results_ready = False
                        st.success(f"Preview: {len(st.session_state.df)} rows (no enrichment)")

            with col_run:
                if st.button("▶️ Run Full Enrichment", key="run_upload", type="primary", use_container_width=True):
                    errors = validate_inputs(
                        require_google_key=enrich_reviews,
                        require_email_config=True
                    )
                    if errors:
                        for error in errors:
                            st.error(error)
                    else:
                        try:
                            scraper = adapter.create_scraper(google_api_key) if enrich_reviews else None
                            df = df_upload.copy()

                            # Step 1: Google Reviews (if enabled)
                            if enrich_reviews:
                                with st.status("⭐ Enriching with Google reviews...", expanded=True) as status:
                                    progress_bar = st.progress(0)

                                    def update_progress(current, total):
                                        progress_bar.progress(current / total)
                                        st.write(f"Processing: {current}/{total}")

                                    df = adapter.enrich_with_reviews(scraper, df, update_progress)
                                    status.update(label="✓ Google reviews added", state="complete")

                            # Step 2: Website & Social (if enabled)
                            if enrich_website:
                                with st.status("🌐 Enriching with website data...", expanded=True) as status:
                                    progress_bar = st.progress(0)

                                    def update_progress(current, total):
                                        progress_bar.progress(current / total)
                                        st.write(f"Processing: {current}/{total}")

                                    df = adapter.enrich_with_website_data(df, update_progress)
                                    status.update(label="✓ Website data added", state="complete")

                            # Step 3: AI Emails (if enabled)
                            if enrich_emails:
                                with st.status("✉️ Generating personalized emails...", expanded=True) as status:
                                    progress_bar = st.progress(0)

                                    def update_progress(current, total):
                                        progress_bar.progress(current / total)
                                        st.write(f"Processing: {current}/{total}")

                                    # Create email generator
                                    generator = adapter.create_email_generator(
                                        llm_model,
                                        llm_api_key,
                                        adapter.DEFAULT_PROMPT_TEMPLATE
                                    )

                                    df = adapter.generate_emails(
                                        df,
                                        generator,
                                        product_description,
                                        update_progress
                                    )
                                    status.update(label="✓ Emails generated", state="complete")

                            # Save to session state
                            st.session_state.df = df
                            st.session_state.results_ready = True
                            st.success(f"✅ Enrichment complete! {len(df)} leads ready")

                        except Exception as e:
                            st.error(f"Error: {str(e)}")
                            import traceback
                            st.code(traceback.format_exc())

        except Exception as e:
            st.error(f"Error reading CSV: {str(e)}")

# ========== RESULTS DISPLAY ==========
if st.session_state.df is not None:
    st.markdown("---")
    st.subheader("📊 Results")

    df_display = st.session_state.df

    # Show metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Rows", len(df_display))
    with col2:
        st.metric("Total Columns", len(df_display.columns))
    with col3:
        if 'Generated Email' in df_display.columns:
            email_count = df_display['Generated Email'].notna().sum()
            st.metric("Emails Generated", email_count)

    # Display dataframe
    st.dataframe(df_display, use_container_width=True)

    # Download button
    csv_data = df_to_csv_download(df_display)
    st.download_button(
        label="⬇️ Download CSV",
        data=csv_data,
        file_name="enriched_leads.csv",
        mime="text/csv",
        use_container_width=True
    )

    # Show preview note
    if not st.session_state.results_ready:
        st.info("💡 This is a preview. Click 'Run Full Enrichment' to process all rows with selected enrichments.")
