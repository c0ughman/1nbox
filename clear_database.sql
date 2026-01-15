-- SQL script to clear all data from the database
-- Run this in Railway PostgreSQL Query tab or via psql

-- Delete in order to respect foreign key constraints
DELETE FROM _1nbox_ai_bitesdigest;
DELETE FROM _1nbox_ai_bitessubscription;
DELETE FROM _1nbox_ai_genieanalysis;
DELETE FROM _1nbox_ai_chatmessage;
DELETE FROM _1nbox_ai_chatconversation;
DELETE FROM _1nbox_ai_comment;
DELETE FROM _1nbox_ai_summary;
DELETE FROM _1nbox_ai_topic;
DELETE FROM _1nbox_ai_user;
DELETE FROM _1nbox_ai_organization;

-- Verify deletion (optional - should return 0 for all)
SELECT 
    (SELECT COUNT(*) FROM _1nbox_ai_organization) as organizations,
    (SELECT COUNT(*) FROM _1nbox_ai_user) as users,
    (SELECT COUNT(*) FROM _1nbox_ai_topic) as topics,
    (SELECT COUNT(*) FROM _1nbox_ai_summary) as summaries;

