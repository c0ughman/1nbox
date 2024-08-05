from _1nbox_ai.models import User, Topic  # Adjust the import to your actual module path

def generate_answer(from_number, body):
    # Check if from_number contains ":" and extract the part after it if present
    if ":" in from_number:
        from_number = from_number.split(":", 1)[1]

    print("GENERATING ANSWER")
    print(from_number)
    print(body)
    
    # Find the user with the matching phone number
    user = User.objects.filter(phone_number=from_number).first()
    if not user:
        return "Error: User not found."

    general_list = []

    # Iterate through the user's topics
    for topic in user.topics:
        try:
            chosen_topic = Topic.objects.get(name=topic)
            # Add the Topic summary to the general list
            general_list.append(chosen_topic.summary)
            
            # Add each cluster summary to the general list
            for cluster in chosen_topic.cluster_summaries:
                for key, value in cluster.items():
                    combined_string = f"{key}: {value}"
                    general_list.append(combined_string)
                    
        except Topic.DoesNotExist:
            # Skip to the next topic if the Topic instance does not exist
            continue
    
        # Print the general list
        print(general_list)
