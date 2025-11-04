async def push_to_telex_simple(
    push_config: PushNotificationConfig,
    agent_msg: dict,
    task_id: str,
    context_id: str,
    user_msg: dict,
) -> bool:
    """
    Simple webhook push with the exact structure that works.
    """
    headers = {
        "Authorization": f"Bearer {push_config.token}",
        "Content-Type": "application/json",
    }

    # Use the EXACT structure from the working example
    payload = {
        "jsonrpc": "2.0",
        "id": task_id,
        "result": {
            "id": task_id,
            "contextId": context_id,
            "status": {
                "state": "completed",
                "timestamp": datetime.utcnow().isoformat(),
                "message": agent_msg,
            },
            "artifacts": [],
            "history": [
                user_msg,
                agent_msg,
            ],  # Include full history like working example
            "kind": "task",
        },
    }

    print(f"[WEBHOOK] Pushing to: {push_config.url}")
    print(f"[WEBHOOK] Task ID: {task_id}")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(push_config.url, headers=headers, json=payload)

            print(f"[WEBHOOK] Response status: {response.status_code}")

            if response.status_code in [200, 202]:
                print(f"[WEBHOOK] ✅ Success! Status: {response.status_code}")
                return True
            else:
                print(f"[WEBHOOK] ❌ Failed with status: {response.status_code}")
                print(f"[WEBHOOK] Response: {response.text}")
                return False

    except Exception as e:
        print(f"[WEBHOOK] ❌ Exception: {traceback.format_exc()}")
        return False


async def process_country_request(
    user_text: str,
    task_id: str,
    context_id: str,
    push_config: PushNotificationConfig,
    original_message_id: str,
):
    """
    Background task to process country request and push result to Telex webhook.
    """
    print(f"[BACKGROUND] Starting processing for task_id={task_id}")

    try:
        # Extract country and process
        country = extract_country(user_text)
        print(f"[BACKGROUND] Extracted country: '{country}'")

        if not country:
            result_text = "Please specify a country (e.g., 'tell me about Kenya')."
        else:
            try:
                result_text = await asyncio.wait_for(
                    country_summary_with_fact(country), timeout=20.0
                )
            except asyncio.TimeoutError:
                result_text = (
                    f"Sorry, gathering information about {country} took too long."
                )
            except Exception as e:
                print(f"[BACKGROUND] Processing error: {traceback.format_exc()}")
                result_text = f"Sorry, I encountered an error processing {country}."

    except Exception as e:
        print(f"[BACKGROUND] Error: {traceback.format_exc()}")
        result_text = f"Sorry, I encountered an error: {str(e)}"

    # Create messages
    agent_msg = _make_agent_message(task_id, result_text)
    user_msg = _make_user_message(user_text, original_message_id)

    # Push result to Telex webhook
    success = await push_to_telex_simple(
        push_config, agent_msg, task_id, context_id, user_msg
    )

    if success:
        print(f"[BACKGROUND] ✅ Completed successfully for task_id={task_id}")
    else:
        print(f"[BACKGROUND] ❌ Failed to deliver result for task_id={task_id}")
