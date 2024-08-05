from django.http import JsonResponse
from _1nbox_ai.models import User, Topic  # Adjust the import to your actual module path

def generate_answer(request):
    if request.method == 'POST':
        try:
            request_data = json.loads(request.body.decode('utf-8'))
            from_number = request_data.get('from_number')
            body = request_data.get('body')

            # Check if from_number contains ":" and extract the part after it if present
            if ":" in from_number:
                from_number = from_number.split(":", 1)[1]

            # Find the user with the matching phone number
            user = User.objects.filter(phone_number=from_number).first()
            
            if not user:
                return JsonResponse({'error': 'User not found'}, status=404)

            general_list = []

            # Iterate through the user's topics
            for topic_name in user.topics:
                # Find the matching Topic instance
                topic = Topic.objects.filter(name=topic_name).first()
                
                if topic:
                    # Add the Topic summary to the general list
                    general_list.append(topic.summary)
                    
                    # Add each cluster summary to the general list
                    general_list.extend(topic.cluster_summaries)

            # Print the general list
            print(general_list)
            return JsonResponse({'success': True, 'data': general_list}, status=200)

        except Exception as e:
            print(f"Error processing request: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)
    else:
        return JsonResponse({'error': 'Only POST requests are allowed'}, status=405)
