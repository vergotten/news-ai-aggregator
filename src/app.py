"""Streamlit web interface for News Aggregator."""
import streamlit as st
import os
import sys
from pathlib import Path
import pandas as pd
import threading
import time
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

st.set_page_config(
    page_title="News Aggregator",
    page_icon="📰",
    layout="wide"
)

from src.utils.translations import TRANSLATIONS

def t(key, **kwargs):
    """Translate key to current language."""
    lang = st.session_state.get('language', 'ru')
    text = TRANSLATIONS.get(lang, TRANSLATIONS['ru']).get(key, key)
    if kwargs:
        return text.format(**kwargs)
    return text

css_path = Path(__file__).parent / "static" / "style.css"
if css_path.exists():
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    st.error("DATABASE_URL not configured")
    st.stop()

try:
    from src.models.database import (
        init_db,
        get_stats_extended,
        get_posts_by_subreddit,
        get_processed_posts,
        get_processed_by_subreddit,
        get_medium_articles,
        get_session,
        RedditPost,
        ProcessedRedditPost,
        MediumArticle,
        TelegramMessage
    )
    from src.config_loader import get_config

    init_db()
    config = get_config()
except Exception as e:
    st.error(f"Initialization error: {e}")
    st.stop()

if 'parsing_active' not in st.session_state:
    st.session_state.parsing_active = False
if 'parsing_status' not in st.session_state:
    st.session_state.parsing_status = ""
if 'parsing_results' not in st.session_state:
    st.session_state.parsing_results = []
if 'processing_active' not in st.session_state:
    st.session_state.processing_active = False
if 'processing_status' not in st.session_state:
    st.session_state.processing_status = ""
if 'processing_results' not in st.session_state:
    st.session_state.processing_results = {}
if 'last_update' not in st.session_state:
    st.session_state.last_update = time.time()
if 'selected_category' not in st.session_state:
    st.session_state.selected_category = t('all_categories')
if 'language' not in st.session_state:
    st.session_state.language = 'ru'

def background_reddit_parse(subreddits, max_posts, sort_by, delay, enable_llm):
    try:
        from src.scrapers.reddit_scraper import scrape_multiple_subreddits

        st.session_state.parsing_active = True
        st.session_state.parsing_status = t('parsing_progress')

        results = scrape_multiple_subreddits(
            subreddits=subreddits,
            max_posts=max_posts,
            sort_by=sort_by,
            delay=delay,
            enable_llm=enable_llm
        )

        st.session_state.parsing_results = results
        st.session_state.parsing_status = t('parsing_complete', count=len(results))

    except Exception as e:
        st.session_state.parsing_status = t('parsing_error', error=str(e))
    finally:
        st.session_state.parsing_active = False
        st.session_state.last_update = time.time()

def background_editorial_process(unprocessed_posts):
    processed_count = 0
    news_count = 0
    error_count = 0

    try:
        from src.services.editorial_service import get_editorial_service

        st.session_state.processing_active = True
        st.session_state.processing_status = "GPT-OSS processing in progress..."

        editorial = get_editorial_service()
        total = len(unprocessed_posts)

        for idx, post in enumerate(unprocessed_posts):
            st.session_state.processing_status = f"Processing {idx + 1}/{total}: {post.title[:40]}..."

            try:
                text = f"{post.title}\n\n{post.selftext or ''}"

                if len(text.strip()) < 50:
                    continue

                result = editorial.process_post(
                    title=post.title,
                    content=post.selftext or '',
                    source='reddit'
                )

                if result.get('error'):
                    error_count += 1
                    continue

                session = get_session()

                processed_post = ProcessedRedditPost(
                    post_id=post.post_id,
                    original_title=post.title,
                    original_text=post.selftext or '',
                    subreddit=post.subreddit,
                    author=post.author,
                    url=post.url,
                    score=post.score,
                    is_news=result.get('is_news', False),
                    original_summary=result.get('original_summary'),
                    rewritten_post=result.get('rewritten_post'),
                    editorial_title=result.get('title'),
                    teaser=result.get('teaser'),
                    image_prompt=result.get('image_prompt'),
                    processed_at=datetime.utcnow(),
                    processing_time=int(result.get('processing_time', 0) * 1000),
                    model_used='gpt-oss:20b'
                )

                session.add(processed_post)
                session.commit()
                session.close()

                processed_count += 1
                if result.get('is_news'):
                    news_count += 1

            except Exception as e:
                error_count += 1
                continue

        st.session_state.processing_results = {
            'processed': processed_count,
            'news': news_count,
            'errors': error_count
        }
        st.session_state.processing_status = f"GPT-OSS complete. {t('processed')}: {processed_count} | {t('news')}: {news_count} | {t('error')}: {error_count}"

    except Exception as e:
        st.session_state.processing_status = f"Processing error: {str(e)}"
    finally:
        st.session_state.processing_active = False
        st.session_state.last_update = time.time()

def format_timedelta(td, lang='ru'):
    total_seconds = int(td.total_seconds())
    if total_seconds < 60:
        return f"{total_seconds} {t('sec')} {t('ago')}"
    elif total_seconds < 3600:
        return f"{total_seconds // 60} {t('min')} {t('ago')}"
    elif total_seconds < 86400:
        return f"{total_seconds // 3600} {t('hour')} {t('ago')}"
    else:
        days = total_seconds // 86400
        return f"{days} {t('days')} {t('ago')}"

col_title, col_spacer, col_lang = st.columns([3, 0.5, 1])

with col_title:
    st.title(t('title'))
    st.caption(t('subtitle'))

with col_lang:
    col_ru, col_en = st.columns(2)
    with col_ru:
        if st.button("🇷🇺 RU", key="lang_ru", use_container_width=True,
                    type="primary" if st.session_state.language == 'ru' else "secondary"):
            st.session_state.language = 'ru'
            st.rerun()
    with col_en:
        if st.button("🇬🇧 EN", key="lang_en", use_container_width=True,
                    type="primary" if st.session_state.language == 'en' else "secondary"):
            st.session_state.language = 'en'
            st.rerun()

if st.session_state.parsing_active or st.session_state.processing_active:
    if st.session_state.parsing_active:
        st.info(st.session_state.parsing_status)
    if st.session_state.processing_active:
        st.info(st.session_state.processing_status)
elif st.session_state.parsing_status and time.time() - st.session_state.last_update < 10:
    st.success(st.session_state.parsing_status)
elif st.session_state.processing_status and time.time() - st.session_state.last_update < 10:
    st.success(st.session_state.processing_status)

col1, col2, col3 = st.columns(3)
with col1:
    if os.getenv("REDDIT_CLIENT_ID"):
        st.success(t('reddit_api'))
    else:
        st.warning(t('reddit_api'))
with col2:
    if os.getenv("TELEGRAM_API_ID"):
        st.success(t('telegram_api'))
    else:
        st.warning(t('telegram_api'))
with col3:
    st.success(t('database'))

st.markdown("---")

try:
    stats = get_stats_extended()
except:
    stats = {
        'reddit_posts': 0,
        'telegram_messages': 0,
        'medium_articles': 0,
        'latest_reddit': None,
        'latest_telegram': None,
        'latest_medium': None
    }

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    t('reddit_tab'),
    t('telegram_tab'),
    t('medium_tab'),
    t('processed_tab'),
    t('analytics_tab'),
    t('viewer_tab')
])

with tab1:
    st.markdown('<div class="reddit-section">', unsafe_allow_html=True)
    st.header(f"{t('reddit_tab')} Parser")

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader(t('settings'))

        all_subreddits = config.get_reddit_subreddits()
        categories = config.get_reddit_categories()

        category_filter = st.selectbox(
            t('filter_category'),
            [t('all_categories')] + categories,
            index=0,
            key="reddit_category"
        )

        st.session_state.selected_category = category_filter

        if category_filter == t('all_categories'):
            filtered_subs = all_subreddits
        else:
            filtered_subs = config.get_reddit_subreddits(category=category_filter)

        if 'reddit_selected' not in st.session_state:
            st.session_state.reddit_selected = []
        if 'reddit_widget_key' not in st.session_state:
            st.session_state.reddit_widget_key = 0

        col_sel1, col_sel2 = st.columns([3, 1])

        with col_sel2:
            st.write("")
            st.write("")
            if st.button(t('select_all'), key="select_all_reddit"):
                st.session_state.reddit_selected = filtered_subs.copy()
                st.session_state.reddit_widget_key += 1
                st.rerun()

        with col_sel1:
            selected_subs = st.multiselect(
                t('subreddits'),
                filtered_subs,
                default=[s for s in st.session_state.reddit_selected if s in filtered_subs],
                key=f"reddit_multiselect_{st.session_state.reddit_widget_key}"
            )
            st.session_state.reddit_selected = selected_subs

        col_a, col_b, col_c, col_d = st.columns(4)
        with col_a:
            max_posts = st.slider(t('max_posts'), 10, 200, 50, key="reddit_max_posts")
        with col_b:
            delay = st.slider(t('delay_sec'), 3, 30, 5, key="reddit_delay")
        with col_c:
            sort_by = st.selectbox(t('sort'), ["hot", "new", "top"], key="reddit_sort")
        with col_d:
            enable_llm = st.checkbox(t('editorial'), value=False, key="reddit_llm")

        parse_button_disabled = st.session_state.parsing_active

        if st.button(
            t('parsing_active') if parse_button_disabled else t('start_parsing'),
            type="primary",
            use_container_width=True,
            key="reddit_parse_btn",
            disabled=parse_button_disabled
        ):
            if not selected_subs:
                st.error(t('select_subreddits'))
            elif not os.getenv("REDDIT_CLIENT_ID"):
                st.error(t('api_not_configured'))
            else:
                st.session_state.parsing_results = []
                st.session_state.parsing_status = ""

                thread = threading.Thread(
                    target=background_reddit_parse,
                    args=(selected_subs, max_posts, sort_by, delay, enable_llm),
                    daemon=True
                )
                thread.start()

                st.success(t('parsing_started'))
                st.info(t('status_at_top'))
                time.sleep(1)
                st.rerun()

        if st.session_state.parsing_results and not st.session_state.parsing_active:
            with st.expander(t('parsing_results'), expanded=True):
                for result in st.session_state.parsing_results:
                    if result.get('success'):
                        msg = f"**r/{result['subreddit']}**: {t('saved')}: {result.get('saved', 0)}, {t('skipped')}: {result.get('skipped', 0)}"
                        if enable_llm and result.get('editorial_processed'):
                            msg += f", {t('editorial')}: {result.get('editorial_processed', 0)}"
                        st.write(msg)
                    else:
                        st.error(f"**r/{result.get('subreddit')}**: {t('error')} - {result.get('error', 'Unknown')}")

                if st.button(t('clear_results'), key="clear_results"):
                    st.session_state.parsing_results = []
                    st.session_state.parsing_status = ""
                    st.rerun()

    with col2:
        st.subheader(t('statistics'))
        st.metric(t('posts'), f"{stats['reddit_posts']:,}")

        if selected_subs:
            st.subheader(t('processed_news'))
            try:
                processed = get_processed_by_subreddit(selected_subs[0], limit=5)
                for post in processed:
                    if post.is_news:
                        with st.expander(f"{t('news_badge')}: {post.editorial_title[:40]}..."):
                            st.write(f"**r/{post.subreddit}** {t('score')}: {post.score}")
                            if post.teaser:
                                st.caption(post.teaser)
                            if post.url:
                                st.link_button(t('open_original'), post.url)
                    else:
                        with st.expander(f"{t('not_news_badge')}: {post.original_title[:40]}..."):
                            st.caption(t('not_news'))
            except Exception as e:
                st.caption(f"{t('error')}: {e}")

    st.markdown('</div>', unsafe_allow_html=True)

with tab2:
    st.markdown('<div class="telegram-section">', unsafe_allow_html=True)
    st.header(f"{t('telegram_tab')} Parser")
    st.info(t('in_development'))
    st.markdown('</div>', unsafe_allow_html=True)

with tab3:
    st.markdown('<div class="medium-section">', unsafe_allow_html=True)
    st.header(f"{t('medium_tab')} Parser")
    st.info(t('in_development'))
    st.markdown('</div>', unsafe_allow_html=True)

with tab4:
    st.header(t('processed_tab'))

    with st.expander(t('preprocessing_control'), expanded=False):
        st.markdown(f"### {t('sync_processing')}")
        st.caption(t('process_raw_posts'))

        col_sync1, col_sync2 = st.columns([2, 1])

        with col_sync1:
            st.markdown(f"**{t('statistics')}:**")
            try:
                session = get_session()
                total_raw = session.query(RedditPost).count()
                total_processed = session.query(ProcessedRedditPost).count()

                from sqlalchemy import exists
                unprocessed_count = session.query(RedditPost).filter(
                    ~exists().where(ProcessedRedditPost.post_id == RedditPost.post_id)
                ).count()

                session.close()

                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    st.metric(t('raw_posts'), total_raw)
                with col_b:
                    st.metric(t('processed'), total_processed)
                with col_c:
                    st.metric(t('unprocessed'), unprocessed_count)

            except Exception as e:
                st.error(t('statistics_error', error=str(e)))
                unprocessed_count = 0

        with col_sync2:
            st.markdown(f"**{t('settings')}:**")
            batch_size = st.number_input(
                t('batch_size'),
                min_value=1,
                max_value=100,
                value=10,
                help=t('batch_size_help'),
                key="batch_size_input"
            )

        st.markdown("---")

        col_btn1, col_btn2, col_btn3 = st.columns(3)

        with col_btn1:
            process_button_disabled = st.session_state.processing_active

            if st.button(
                t('processing_active') if process_button_disabled else t('start_processing'),
                type="primary",
                use_container_width=True,
                disabled=process_button_disabled,
                key="start_processing_btn"
            ):
                if unprocessed_count == 0:
                    st.info(t('no_unprocessed'))
                else:
                    try:
                        from sqlalchemy import exists

                        session = get_session()
                        unprocessed_posts = session.query(RedditPost).filter(
                            ~exists().where(ProcessedRedditPost.post_id == RedditPost.post_id)
                        ).limit(batch_size).all()
                        session.close()

                        if not unprocessed_posts:
                            st.warning(t('no_posts_process'))
                        else:
                            st.session_state.processing_status = ""
                            st.session_state.processing_results = {}

                            thread = threading.Thread(
                                target=background_editorial_process,
                                args=(unprocessed_posts,),
                                daemon=True
                            )
                            thread.start()

                            st.success(t('processing_started', count=len(unprocessed_posts)))
                            st.info(t('status_at_top'))
                            time.sleep(1)
                            st.rerun()

                    except Exception as e:
                        st.error(f"{t('error')}: {e}")
                        import traceback
                        st.code(traceback.format_exc())

        with col_btn2:
            if st.button(t('show_unprocessed'), use_container_width=True, key="show_unprocessed_btn"):
                try:
                    from sqlalchemy import exists

                    session = get_session()
                    unprocessed = session.query(RedditPost).filter(
                        ~exists().where(ProcessedRedditPost.post_id == RedditPost.post_id)
                    ).order_by(RedditPost.scraped_at.desc()).limit(20).all()
                    session.close()

                    if unprocessed:
                        st.markdown(f"### {t('unprocessed_top20')}")
                        for post in unprocessed:
                            st.caption(f"r/{post.subreddit} {post.title[:60]}...")
                    else:
                        st.info(t('all_processed'))

                except Exception as e:
                    st.error(f"{t('error')}: {e}")

        with col_btn3:
            if st.button(t('clear_processed'), use_container_width=True, key="clear_processed_btn"):
                if st.checkbox(t('confirm_deletion'), key="confirm_delete"):
                    try:
                        session = get_session()
                        deleted = session.query(ProcessedRedditPost).delete()
                        session.commit()
                        session.close()

                        st.success(t('deleted_records', count=deleted))
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"{t('error')}: {e}")

        if st.session_state.processing_results and not st.session_state.processing_active:
            st.markdown("---")
            col_res1, col_res2, col_res3 = st.columns(3)
            with col_res1:
                st.metric(t('processed'), st.session_state.processing_results.get('processed', 0))
            with col_res2:
                st.metric(t('news'), st.session_state.processing_results.get('news', 0))
            with col_res3:
                st.metric(t('error'), st.session_state.processing_results.get('errors', 0))

    st.markdown("---")

    col1, col2 = st.columns([3, 1])

    with col1:
        show_mode = st.radio(t('show'), [t('show_news_only'), t('show_all_processed')], horizontal=True)
        news_only = (show_mode == t('show_news_only'))

        try:
            processed = get_processed_posts(limit=50, news_only=news_only)
            st.caption(t('found', count=len(processed)))

            for post in processed:
                if post.is_news:
                    with st.container():
                        st.markdown(f"### {post.editorial_title}")
                        st.caption(f"r/{post.subreddit} {post.author} {t('score')}: {post.score}")

                        if post.teaser:
                            st.markdown(f"*{post.teaser}*")

                        col_a, col_b, col_c = st.columns(3)
                        with col_a:
                            if post.rewritten_post:
                                with st.expander(t('rewritten_text')):
                                    st.write(post.rewritten_post)
                        with col_b:
                            if post.image_prompt:
                                with st.expander(t('image_prompt')):
                                    st.code(post.image_prompt)
                        with col_c:
                            st.caption(t('processed_at', date=post.processed_at.strftime('%Y-%m-%d %H:%M')))
                            st.caption(t('time_ms', ms=post.processing_time))
                            st.caption(f"{post.model_used or 'gpt-oss'}")

                        if post.url:
                            st.link_button(t('open_original'), post.url)

                        st.divider()
                else:
                    with st.expander(f"{t('not_news_badge')}: {post.original_title[:60]}..."):
                        st.caption(f"r/{post.subreddit} {t('not_news')}")
                        st.caption(t('processed_at', date=post.processed_at.strftime('%Y-%m-%d %H:%M')))

        except Exception as e:
            st.error(f"{t('error')}: {e}")

    with col2:
        st.subheader(t('statistics'))
        try:
            session = get_session()
            total = session.query(ProcessedRedditPost).count()
            news_count = session.query(ProcessedRedditPost).filter_by(is_news=True).count()
            session.close()

            st.metric(t('total_processed'), total)
            st.metric(t('news'), news_count)
            if total > 0:
                st.metric(t('news_percent'), f"{(news_count / total * 100):.1f}%")
        except Exception as e:
            st.error(t('statistics_error', error=str(e)))

with tab5:
    st.header(t('analytics_tab'))

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Reddit", f"{stats['reddit_posts']:,}")
    with col2:
        st.metric("Telegram", f"{stats['telegram_messages']:,}")
    with col3:
        st.metric("Medium", f"{stats['medium_articles']:,}")
    with col4:
        total = stats['reddit_posts'] + stats['telegram_messages'] + stats['medium_articles']
        st.metric(t('total'), f"{total:,}")

    st.markdown("---")

    if total > 0:
        st.subheader(t('activity'))

        chart_data = pd.DataFrame({
            t('platform'): ['Reddit', 'Telegram', 'Medium'],
            t('records_count'): [
                stats['reddit_posts'],
                stats['telegram_messages'],
                stats['medium_articles']
            ]
        })
        st.bar_chart(chart_data.set_index(t('platform')))
    else:
        st.info(t('no_data'))

with tab6:
    st.header(t('viewer_tab'))

    data_source = st.selectbox(
        t('data_source'),
        [t('reddit_raw'), t('reddit_processed'), t('telegram_messages'), t('medium_articles')]
    )

    col1, col2 = st.columns([1, 1])
    with col1:
        limit = st.slider(t('records_count'), 10, 500, 100, key="viewer_limit")

    with col2:
        if data_source == t('reddit_raw'):
            sort_options = {
                t('sort_scraped_desc'): "scraped_at_desc",
                t('sort_scraped_asc'): "scraped_at_asc",
                t('sort_created_desc'): "created_utc_desc",
                t('sort_created_asc'): "created_utc_asc",
                t('sort_score_desc'): "score_desc",
                t('sort_score_asc'): "score_asc"
            }
        elif data_source == t('reddit_processed'):
            sort_options = {
                t('sort_processed_desc'): "processed_at_desc",
                t('sort_processed_asc'): "processed_at_asc",
                t('sort_score_desc'): "score_desc",
                t('sort_score_asc'): "score_asc"
            }
        else:
            sort_options = {
                t('sort_scraped_desc'): "scraped_at_desc",
                t('sort_scraped_asc'): "scraped_at_asc"
            }

        sort_by = st.selectbox(
            t('sort_by'),
            list(sort_options.keys()),
            key="viewer_sort_selector"
        )
        sort_value = sort_options[sort_by]

    try:
        session = get_session()

        if data_source == t('reddit_raw'):
            st.subheader(t('raw_reddit_posts'))

            query = session.query(RedditPost)

            if sort_value == "scraped_at_desc":
                query = query.order_by(RedditPost.scraped_at.desc())
            elif sort_value == "scraped_at_asc":
                query = query.order_by(RedditPost.scraped_at.asc())
            elif sort_value == "created_utc_desc":
                query = query.order_by(RedditPost.created_utc.desc())
            elif sort_value == "created_utc_asc":
                query = query.order_by(RedditPost.created_utc.asc())
            elif sort_value == "score_desc":
                query = query.order_by(RedditPost.score.desc())
            elif sort_value == "score_asc":
                query = query.order_by(RedditPost.score.asc())

            posts = query.limit(limit).all()

            if posts:
                for post in posts:
                    has_vector = post.qdrant_id is not None
                    vector_badge = t('vectorized') if has_vector else t('no_vector')

                    now = datetime.now(timezone.utc)
                    created_time = post.created_utc.replace(tzinfo=timezone.utc) if post.created_utc.tzinfo is None else post.created_utc
                    scraped_time = post.scraped_at.replace(tzinfo=timezone.utc) if post.scraped_at.tzinfo is None else post.scraped_at

                    time_since_created = now - created_time
                    time_since_scraped = now - scraped_time

                    with st.expander(f"r/{post.subreddit} {post.title[:80]}"):
                        col_badge1, col_badge2, col_badge3 = st.columns([1, 1, 2])
                        with col_badge1:
                            st.caption(vector_badge)
                        with col_badge2:
                            if has_vector:
                                st.caption(f"`{str(post.qdrant_id)[:8]}...`")

                        st.markdown("---")

                        col_time1, col_time2 = st.columns(2)
                        with col_time1:
                            st.markdown(f"**{t('published_reddit')}**")
                            st.info(f"{post.created_utc.strftime('%Y-%m-%d %H:%M:%S UTC')}")
                            st.caption(format_timedelta(time_since_created, st.session_state.language))
                        with col_time2:
                            st.markdown(f"**{t('received_db')}**")
                            st.success(f"{post.scraped_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
                            st.caption(format_timedelta(time_since_scraped, st.session_state.language))

                        st.markdown("---")

                        col_a, col_b = st.columns([2, 1])

                        with col_a:
                            st.markdown(f"**{t('original_title')}**")
                            st.write(post.title)

                            st.markdown(f"**{t('original_text')}**")
                            if post.selftext:
                                st.text_area(
                                    t('post_text'),
                                    post.selftext,
                                    height=200,
                                    key=f"raw_{post.id}",
                                    label_visibility="collapsed"
                                )
                            else:
                                st.caption(f"_{t('text_missing')}_")

                        with col_b:
                            st.metric(t('score'), post.score)
                            st.metric(t('comments'), post.num_comments)
                            st.caption(f"**{t('author')}** u/{post.author}")

                            if has_vector:
                                st.success(t('in_qdrant'))
                                with st.expander(t('qdrant_uuid')):
                                    st.code(str(post.qdrant_id))
                            else:
                                st.warning(t('no_vector'))

                            if post.url:
                                st.link_button(t('open_original'), post.url)
            else:
                st.info(t('no_data_available'))

        elif data_source == t('reddit_processed'):
            st.subheader(t('processed_gpt'))

            query = session.query(ProcessedRedditPost)

            if sort_value == "processed_at_desc":
                query = query.order_by(ProcessedRedditPost.processed_at.desc())
            elif sort_value == "processed_at_asc":
                query = query.order_by(ProcessedRedditPost.processed_at.asc())
            elif sort_value == "score_desc":
                query = query.order_by(ProcessedRedditPost.score.desc())
            elif sort_value == "score_asc":
                query = query.order_by(ProcessedRedditPost.score.asc())

            posts = query.limit(limit).all()

            if posts:
                for post in posts:
                    status_icon = t('news_badge') if post.is_news else t('not_news_badge')
                    title_display = post.editorial_title if post.editorial_title else post.original_title

                    raw_post = session.query(RedditPost).filter_by(post_id=post.post_id).first()
                    has_vector = raw_post and raw_post.qdrant_id is not None

                    now = datetime.now(timezone.utc)

                    with st.expander(f"{status_icon} r/{post.subreddit} {title_display[:80]}"):
                        col_badge1, col_badge2, col_badge3, col_badge4 = st.columns([1, 1, 1, 1])
                        with col_badge1:
                            if post.is_news:
                                st.success(t('news_badge'))
                            else:
                                st.error(t('not_news_badge'))
                        with col_badge2:
                            if has_vector:
                                st.info(t('vectorized'))
                            else:
                                st.warning(t('no_vector'))
                        with col_badge3:
                            st.caption(f"{post.processing_time}ms")
                        with col_badge4:
                            st.caption(f"{post.model_used or 'gpt-oss'}")

                        st.markdown("---")

                        if raw_post:
                            col_timeline1, col_timeline2, col_timeline3 = st.columns(3)
                            created_time = raw_post.created_utc.replace(tzinfo=timezone.utc) if raw_post.created_utc.tzinfo is None else raw_post.created_utc
                            scraped_time = raw_post.scraped_at.replace(tzinfo=timezone.utc) if raw_post.scraped_at.tzinfo is None else raw_post.scraped_at
                            processed_time = post.processed_at.replace(tzinfo=timezone.utc) if post.processed_at.tzinfo is None else post.processed_at

                            with col_timeline1:
                                st.markdown(f"**{t('published')}**")
                                st.info(f"{raw_post.created_utc.strftime('%Y-%m-%d %H:%M')}")
                                st.caption(format_timedelta(now - created_time, st.session_state.language))
                            with col_timeline2:
                                st.markdown(f"**{t('received')}**")
                                st.success(f"{raw_post.scraped_at.strftime('%Y-%m-%d %H:%M')}")
                                st.caption(format_timedelta(now - scraped_time, st.session_state.language))
                            with col_timeline3:
                                st.markdown(f"**{t('gpt_processed')}**")
                                st.warning(f"{post.processed_at.strftime('%Y-%m-%d %H:%M')}")
                                st.caption(format_timedelta(now - processed_time, st.session_state.language))

                        st.markdown("---")

                        if post.is_news:
                            col_orig, col_processed = st.columns(2)

                            with col_orig:
                                st.markdown(f"### {t('original_section')}")
                                st.markdown(f"**{t('original_title')}**")
                                st.info(post.original_title)

                                st.markdown(f"**{t('original_text')}**")
                                if post.original_text:
                                    st.text_area(
                                        t('original_text'),
                                        post.original_text,
                                        height=300,
                                        key=f"orig_{post.id}",
                                        label_visibility="collapsed"
                                    )
                                else:
                                    st.caption(f"_{t('text_missing')}_")

                            with col_processed:
                                st.markdown(f"### {t('processed_section')}")
                                st.markdown(f"**{t('editorial_title')}**")
                                st.success(post.editorial_title)

                                if post.teaser:
                                    st.markdown(f"**{t('teaser')}**")
                                    st.write(f"*{post.teaser}*")

                                st.markdown(f"**{t('rewritten_text')}**")
                                if post.rewritten_post:
                                    st.text_area(
                                        t('rewritten_text'),
                                        post.rewritten_post,
                                        height=300,
                                        key=f"proc_{post.id}",
                                        label_visibility="collapsed"
                                    )

                                if post.image_prompt:
                                    st.markdown(f"**{t('image_prompt')}**")
                                    st.code(post.image_prompt, language="text")

                            st.markdown("---")
                            col_meta1, col_meta2, col_meta3, col_meta4 = st.columns(4)
                            with col_meta1:
                                st.metric(t('score'), post.score)
                            with col_meta2:
                                st.caption(f"**{t('author')}** u/{post.author}")
                            with col_meta3:
                                st.caption(f"**{t('processing')}** {post.processing_time}ms")
                            with col_meta4:
                                if has_vector and raw_post:
                                    st.success(t('in_qdrant'))
                                else:
                                    st.warning(t('no_vector'))

                            if post.url:
                                st.link_button(t('open_original'), post.url)
                        else:
                            st.warning(f"**{t('not_news')}**")
                            st.caption(f"{t('original_title')}: {post.original_title}")
                            st.caption(f"r/{post.subreddit} u/{post.author}")
            else:
                st.info(t('no_data_available'))

        session.close()

        st.markdown("---")
        st.subheader(t('vectorization_stats'))

        col_stat1, col_stat2, col_stat3 = st.columns(3)

        session = get_session()
        total_posts = session.query(RedditPost).count()
        vectorized_posts = session.query(RedditPost).filter(RedditPost.qdrant_id.isnot(None)).count()
        session.close()

        with col_stat1:
            st.metric(t('total_posts'), total_posts)
        with col_stat2:
            st.metric(t('vectorized'), vectorized_posts)
        with col_stat3:
            if total_posts > 0:
                percentage = (vectorized_posts / total_posts) * 100
                st.metric(t('vectorization_percent'), f"{percentage:.1f}%")
            else:
                st.metric(t('vectorization_percent'), "0%")

    except Exception as e:
        st.error(t('data_load_error', error=str(e)))
        import traceback
        st.code(traceback.format_exc())

st.markdown("---")
col_f1, col_f2 = st.columns([3, 1])
with col_f1:
    st.caption("PostgreSQL • Docker • N8N • Ollama • GPT-OSS")
with col_f2:
    if st.button(f"{'🔄 ' if st.session_state.language == 'en' else '🔄 '}{t('clear_results') if st.session_state.language == 'ru' else 'Refresh'}", key="refresh_btn"):
        st.rerun()

if st.session_state.parsing_active or st.session_state.processing_active:
    time.sleep(5)
    st.rerun()