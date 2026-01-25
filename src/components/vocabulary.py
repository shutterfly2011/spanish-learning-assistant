import streamlit as st

from session_state import (
    get_vocabulary,
    update_vocabulary_status,
    clear_vocabulary,
    add_message,
)


def render_vocabulary_sidebar():
    """Render the vocabulary tracker in the sidebar."""
    with st.sidebar:
        st.header("Vocabulary Tracker")

        vocabulary = get_vocabulary()

        if not vocabulary:
            st.info("Words you look up will appear here.")
            return

        # Stats
        total = len(vocabulary)
        learned = sum(1 for v in vocabulary if v.status == "learned")
        learning = sum(1 for v in vocabulary if v.status == "learning")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total", total)
        with col2:
            st.metric("Learning", learning)
        with col3:
            st.metric("Learned", learned)

        st.divider()

        # Filter
        filter_status = st.selectbox(
            "Filter by status",
            options=["all", "new", "learning", "learned"],
            key="vocab_filter",
        )

        # Word list
        filtered_vocab = vocabulary
        if filter_status != "all":
            filtered_vocab = [v for v in vocabulary if v.status == filter_status]

        for item in filtered_vocab:
            with st.container():
                col1, col2 = st.columns([3, 1])
                with col1:
                    # Clickable word to re-query
                    if st.button(
                        f"**{item.word}** ({item.word_type})",
                        key=f"vocab_{item.word}",
                        help=item.meaning,
                        use_container_width=True,
                    ):
                        # Add the word as a new user message to re-analyze
                        add_message("user", item.word)
                        st.rerun()

                with col2:
                    # Status indicator and toggle
                    status_colors = {
                        "new": "gray",
                        "learning": "orange",
                        "learned": "green",
                    }
                    status_emoji = {
                        "new": "",
                        "learning": "",
                        "learned": "",
                    }

                    current_status = item.status
                    next_status = {
                        "new": "learning",
                        "learning": "learned",
                        "learned": "new",
                    }

                    if st.button(
                        status_emoji.get(current_status, ""),
                        key=f"status_{item.word}",
                        help=f"Status: {current_status}. Click to change.",
                    ):
                        update_vocabulary_status(item.word, next_status[current_status])
                        st.rerun()

        st.divider()

        # Clear button
        if st.button("Clear All", type="secondary", use_container_width=True):
            clear_vocabulary()
            st.rerun()
