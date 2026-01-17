from django.core.management.base import BaseCommand
from ...news import (
    get_articles_from_rss,
    extract_significant_words,
    sort_words_by_rarity,
    cluster_articles,
    merge_clusters,
    apply_minimum_articles_and_reassign,
    merge_clusters_by_percentage,
    get_openai_response,
    get_final_summary,
    calculate_cluster_difference,
    calculate_summary_difference,
    clean_clusters_for_storage,
    parse_json_with_repair
)
from ...models import Topic, Organization, Summary
import traceback
import logging
from collections import Counter
from datetime import datetime, timedelta
import pytz
import json

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('cluster_news_processing.log'),
        logging.StreamHandler()
    ]
)

class Command(BaseCommand):
    help = 'Fetch and cluster news every 15 minutes, conditionally summarize'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=1, help='Number of days to look back')
        parser.add_argument('--common_word_threshold', type=int, default=2, help='Number of common words required for clustering')
        parser.add_argument('--top_words_to_consider', type=int, default=3, help='Number of top words to consider for clustering')
        parser.add_argument('--merge_threshold', type=int, default=2, help='Number of common words required to merge clusters')
        parser.add_argument('--min_articles', type=int, default=3, help='Minimum number of articles per cluster')
        parser.add_argument('--join_percentage', type=float, default=0.5, help='Percentage of matching words required to join clusters from misc')
        parser.add_argument('--final_merge_percentage', type=float, default=0.5, help='Percentage of matching words required to merge clusters')
        parser.add_argument('--sentences_final_summary', type=int, default=3, help='Amount of sentences per topic in the final summary')
        parser.add_argument('--title_only', action='store_true', help='If set, clustering will only use article titles')
        parser.add_argument('--all_words', action='store_true', help='If set, clustering will include all words, not just capitalized ones')
        parser.add_argument('--cleanup', action='store_true', help='If set, will cleanup old summaries (30+ days)')

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting cluster news processing...'))
        
        try:
            # Run cleanup if requested
            if options['cleanup']:
                self.cleanup_old_summaries()
            
            # Process all topics
            self.process_all_topics(
                days_back=options['days'],
                common_word_threshold=options['common_word_threshold'],
                top_words_to_consider=options['top_words_to_consider'],
                merge_threshold=options['merge_threshold'],
                min_articles=options['min_articles'],
                join_percentage=options['join_percentage'],
                final_merge_percentage=options['final_merge_percentage'],
                sentences_final_summary=options['sentences_final_summary'],
                title_only=options['title_only'],
                all_words=options['all_words']
            )
            
            self.stdout.write(self.style.SUCCESS('Cluster news processing completed successfully.'))
        except Exception as e:
            self.stderr.write(self.style.ERROR('Error during cluster news processing:'))
            self.stderr.write(self.style.ERROR(str(e)))
            self.stderr.write(self.style.ERROR(traceback.format_exc()))

    def cleanup_old_summaries(self):
        """Delete summaries older than 30 days"""
        logging.info("==== Starting cleanup of old summaries ====")
        
        cutoff_date = datetime.now(pytz.utc) - timedelta(days=30)
        old_summaries = Summary.objects.filter(created_at__lt=cutoff_date)
        count = old_summaries.count()
        
        if count > 0:
            old_summaries.delete()
            logging.info(f"🗑️  Deleted {count} summaries older than 30 days")
        else:
            logging.info("No old summaries to delete")
        
        logging.info("==== Finished cleanup ====")

    def process_all_topics(self, days_back=1, common_word_threshold=2, top_words_to_consider=3,
                          merge_threshold=2, min_articles=3, join_percentage=0.5,
                          final_merge_percentage=0.5, sentences_final_summary=3, 
                          title_only=False, all_words=False):
        
        logging.info("==== Starting process_all_topics ====")
        
        # Get all active organizations (no time check!)
        active_organizations = Organization.objects.exclude(plan='inactive')
        
        for organization in active_organizations:
            logging.info(f"🔄 Processing organization: {organization.name}")
            
            for topic in organization.topics.all():
                try:
                    self.process_topic(
                        topic, 
                        days_back, 
                        common_word_threshold, 
                        top_words_to_consider,
                        merge_threshold, 
                        min_articles, 
                        join_percentage,
                        final_merge_percentage, 
                        sentences_final_summary, 
                        title_only, 
                        all_words
                    )
                except Exception as e:
                    logging.error(f"❌ Failed to process topic {topic.name}: {str(e)}")
                    logging.error(traceback.format_exc())
                    continue
        
        logging.info("==== Finished process_all_topics ====")

    def process_topic(self, topic, days_back=1, common_word_threshold=2, top_words_to_consider=3,
                     merge_threshold=2, min_articles=3, join_percentage=0.5,
                     final_merge_percentage=0.5, sentences_final_summary=3, 
                     title_only=False, all_words=False):
        
        try:
            logging.info(f"📰 Starting processing for topic: {topic.name}")
            
            # Validate topic configuration
            if not topic.sources:
                logging.warning(f"Topic {topic.name} has no sources, skipping")
                return
            
            # Step 1: Fetch articles from RSS (last 24 hours)
            all_articles = []
            failed_sources = []
            successful_sources = []
            
            for url in topic.sources:
                try:
                    articles = get_articles_from_rss(url, days_back)
                    if articles:
                        all_articles.extend(articles)
                        successful_sources.append(url)
                        logging.info(f"✅ Retrieved {len(articles)} articles from {url}")
                    else:
                        failed_sources.append((url, "No articles retrieved"))
                except Exception as e:
                    logging.error(f"❌ Error fetching RSS from {url}: {str(e)}")
                    failed_sources.append((url, str(e)))
                    continue
            
            if not all_articles:
                logging.warning(f"No articles found for topic {topic.name}, skipping")
                return
            
            # Cap articles at 777
            all_articles = all_articles[:777]
            number_of_articles = len(all_articles)
            logging.info(f"📊 Total articles collected: {number_of_articles}")
            
            # Step 2: Extract significant words
            word_counts = Counter()
            for article in all_articles:
                try:
                    if title_only:
                        article['significant_words'] = extract_significant_words(
                            article['title'], title_only=True, all_words=all_words
                        )
                    else:
                        title_words = extract_significant_words(
                            article['title'], title_only=False, all_words=all_words
                        )
                        content_words = extract_significant_words(
                            article['content'], title_only=False, all_words=all_words
                        )
                        article['significant_words'] = title_words + [
                            w for w in content_words if w not in title_words
                        ]
                    word_counts.update(article['significant_words'])
                except Exception as e:
                    logging.error(f"Error extracting words: {str(e)}")
                    continue
            
            # Sort words by rarity
            for article in all_articles:
                try:
                    article['significant_words'] = sort_words_by_rarity(
                        article['significant_words'], word_counts
                    )
                except Exception as e:
                    logging.error(f"Error sorting words: {str(e)}")
                    continue
            
            # Step 3: Cluster articles
            try:
                clusters = cluster_articles(
                    all_articles, common_word_threshold, top_words_to_consider, title_only
                )
                merged_clusters = merge_clusters(clusters, merge_threshold)
                clusters_with_min_articles = apply_minimum_articles_and_reassign(
                    merged_clusters, min_articles, join_percentage
                )
                final_clusters = merge_clusters_by_percentage(
                    clusters_with_min_articles, final_merge_percentage
                )
                
                logging.info(f"🔗 Generated {len(final_clusters)} clusters for topic {topic.name}")
                
            except Exception as e:
                logging.error(f"Error in clustering: {str(e)}")
                return
            
            # Step 4: Check if we should generate summaries
            self.conditionally_generate_summaries(
                topic,
                final_clusters,
                number_of_articles,
                sentences_final_summary
            )
            
        except Exception as e:
            logging.error(f"Critical error processing topic {topic.name}: {str(e)}")
            logging.error(traceback.format_exc())

    def conditionally_generate_summaries(self, topic, current_clusters, number_of_articles, sentences_final_summary):
        """
        Check if clusters changed >40%, generate cluster summaries if needed.
        Then check if cluster summaries changed >40%, generate final summary if needed.
        """
        try:
            # Get the last Summary record for comparison
            last_summary = Summary.objects.filter(topic=topic).order_by('-created_at').first()
            
            # If no previous summary, generate everything
            if not last_summary:
                logging.info(f"No previous summary found for {topic.name}, generating new summary")
                self.generate_and_save_full_summary(
                    topic, current_clusters, number_of_articles, sentences_final_summary
                )
                return
            
            # Get previous clusters from last summary
            previous_clusters = last_summary.clusters if last_summary.clusters else []
            
            # Calculate cluster difference
            cluster_diff = calculate_cluster_difference(current_clusters, previous_clusters)
            logging.info(f"📊 Cluster difference: {cluster_diff:.2%} (threshold: 40%)")
            
            if cluster_diff < 0.40:
                logging.info(f"✋ Clusters didn't change enough (<40%), keeping existing summary")
                # Update topic's current_clusters for next comparison
                topic.current_clusters = clean_clusters_for_storage(current_clusters)
                topic.save(update_fields=['current_clusters'])
                return
            
            # Clusters changed enough, generate new cluster summaries
            logging.info(f"✅ Clusters changed >40%, generating new cluster summaries")
            
            new_cluster_summaries = []
            for i, cluster in enumerate(current_clusters):
                try:
                    logging.info(f"Summarizing cluster {i+1}/{len(current_clusters)}: {', '.join(cluster['common_words'])}")
                    summary_text = get_openai_response(cluster)
                    new_cluster_summaries.append(summary_text)
                except Exception as e:
                    logging.error(f"Error summarizing cluster: {str(e)}")
                    # Use a placeholder
                    new_cluster_summaries.append(f"Error generating summary for cluster: {', '.join(cluster['common_words'])}")
            
            # Check if cluster summaries changed enough for new final summary
            previous_cluster_summaries = last_summary.cluster_summaries if last_summary.cluster_summaries else []
            summary_diff = calculate_summary_difference(new_cluster_summaries, previous_cluster_summaries)
            logging.info(f"📊 Cluster summaries difference: {summary_diff:.2%} (threshold: 40%)")
            
            if summary_diff < 0.40:
                logging.info(f"✋ Cluster summaries didn't change enough (<40%), not generating new final summary")
                # But still update current_clusters
                topic.current_clusters = clean_clusters_for_storage(current_clusters)
                topic.save(update_fields=['current_clusters'])
                return
            
            # Cluster summaries changed enough, generate final summary
            logging.info(f"✅ Cluster summaries changed >40%, generating new final summary")
            
            try:
                final_summary_json = get_final_summary(
                    new_cluster_summaries,
                    sentences_final_summary,
                    topic.prompt if topic.prompt else None,
                    topic.organization.description if topic.organization.description else ""
                )
                
                # Parse JSON with repair logic
                final_summary_data = parse_json_with_repair(final_summary_json)
                
                logging.info(f"✅ Successfully generated final summary")
                
            except Exception as e:
                logging.error(f"Error generating final summary: {str(e)}")
                logging.error(traceback.format_exc())
                final_summary_data = {
                    "summary": [{"title": "Error", "content": f"Failed to generate summary: {str(e)}"}],
                    "questions": ["What happened?", "Why did it happen?", "What's next?"],
                }
            
            # Extract questions
            questions = json.dumps(final_summary_data.get('questions', []))
            
            # Clean clusters for storage
            cleaned_clusters = clean_clusters_for_storage(current_clusters)
            
            # Create new Summary record
            try:
                new_summary = Summary.objects.create(
                    topic=topic,
                    final_summary=final_summary_data,
                    clusters=cleaned_clusters,
                    cluster_summaries=new_cluster_summaries,
                    number_of_articles=number_of_articles,
                    questions=questions
                )
                
                # Update topic's current_clusters
                topic.current_clusters = cleaned_clusters
                topic.save(update_fields=['current_clusters'])
                
                logging.info(f"💾 Successfully saved new summary for topic {topic.name} (ID: {new_summary.id})")
                
            except Exception as e:
                logging.error(f"Database error creating summary: {str(e)}")
                
        except Exception as e:
            logging.error(f"Error in conditionally_generate_summaries: {str(e)}")
            logging.error(traceback.format_exc())

    def generate_and_save_full_summary(self, topic, clusters, number_of_articles, sentences_final_summary):
        """Generate both cluster summaries and final summary (for first run)"""
        try:
            # Generate cluster summaries
            cluster_summaries = []
            for i, cluster in enumerate(clusters):
                try:
                    logging.info(f"Summarizing cluster {i+1}/{len(clusters)}: {', '.join(cluster['common_words'])}")
                    summary_text = get_openai_response(cluster)
                    cluster_summaries.append(summary_text)
                except Exception as e:
                    logging.error(f"Error summarizing cluster: {str(e)}")
                    cluster_summaries.append(f"Error generating summary for cluster: {', '.join(cluster['common_words'])}")
            
            # Generate final summary
            try:
                final_summary_json = get_final_summary(
                    cluster_summaries,
                    sentences_final_summary,
                    topic.prompt if topic.prompt else None,
                    topic.organization.description if topic.organization.description else ""
                )
                
                final_summary_data = parse_json_with_repair(final_summary_json)
                logging.info(f"✅ Successfully generated final summary")
                
            except Exception as e:
                logging.error(f"Error generating final summary: {str(e)}")
                final_summary_data = {
                    "summary": [{"title": "Error", "content": f"Failed to generate summary: {str(e)}"}],
                    "questions": ["What happened?", "Why did it happen?", "What's next?"],
                }
            
            # Extract questions
            questions = json.dumps(final_summary_data.get('questions', []))
            
            # Clean clusters
            cleaned_clusters = clean_clusters_for_storage(clusters)
            
            # Create Summary record
            new_summary = Summary.objects.create(
                topic=topic,
                final_summary=final_summary_data,
                clusters=cleaned_clusters,
                cluster_summaries=cluster_summaries,
                number_of_articles=number_of_articles,
                questions=questions
            )
            
            # Update topic's current_clusters
            topic.current_clusters = cleaned_clusters
            topic.save(update_fields=['current_clusters'])
            
            logging.info(f"💾 Successfully saved first summary for topic {topic.name} (ID: {new_summary.id})")
            
        except Exception as e:
            logging.error(f"Error in generate_and_save_full_summary: {str(e)}")
            logging.error(traceback.format_exc())

