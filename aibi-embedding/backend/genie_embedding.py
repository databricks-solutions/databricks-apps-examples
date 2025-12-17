import requests
import json
import time
import pandas as pd
from dotenv import load_dotenv
import os


# Function for retrieving a Databricks token which will be used to make API calls to Databricks
def get_databricks_oauth_token():
    # Pull Environment Variables from .env file
    load_dotenv()
    databricks_host = os.environ['DATABRICKS_HOST']
    databricks_client_id = os.environ['DATABRICKS_CLIENT_ID']
    databricks_client_secret = os.environ['DATABRICKS_CLIENT_SECRET']

    # Make M2M OAuth Request to Databricks server to get a Databricks Access Token
    token_url = f"https://{databricks_host}/oidc/v1/token"

    payload = {
        "grant_type": "client_credentials",
        "client_id": databricks_client_id,
        "client_secret": databricks_client_secret,
        "scope": "all-apis"
    }

    response = requests.post(token_url, data=payload)
    token_data = response.json()

    # Store the access token and its expiration time
    access_token = token_data["access_token"]
    expires_in = token_data['expires_in']
    expiration_time = time.time() + expires_in

    if response.status_code == 200:
        return {'access_token':access_token, 'expiration_time':expiration_time}
    else:
        raise Exception(f"Failed to get token: {response.status_code}, {response.text}")

# Function for checking Databricks token for expiry, and renews if necessary
def is_token_valid(token):
    current_time = time.time()  # Get the current time in Unix timestamp format
    # If the token is not expired, return the same token
    if current_time < token['expiration_time']:
       return token
    # If the token expired, request a new access token
    else:
       return get_databricks_oauth_token()
    
# In this example, we have one Genie Space for each customer.
# This function checks the user's company and determines which Genie Space ID to retrieve from the environment varible.
# In production, you could use a database to store this mapping
def get_genie_space_id(user_company):
    if user_company.lower() == 'apex':
       return os.environ['DATABRICKS_GENIE_SPACE_ID_APEX']
    elif user_company.lower() == 'synergy':
       return os.environ['DATABRICKS_GENIE_SPACE_ID_SYNERGY']
    else:
       raise Exception(f"Failed to get genie space for: {user_company}")

# Function for starting a new conversation with Genie   
def new_genie_conversation(space_id, content, token, databricks_host):
    # First, we check that the access token is valid
    token = is_token_valid(token)

    # Then, we make an API request to the Genie space 
    url = f"https://{databricks_host}/api/2.0/genie/spaces/{space_id}/start-conversation"

    headers = {
        "Authorization": f"Bearer {token['access_token']}",
        "Content-Type": "application/json"
    }

    payload = {
        "content": content
    }

    response = requests.post(url, headers=headers, data=json.dumps(payload))

    # Finally, we check the response to see if the API call was succesful
    # This request may fail if you don't have the right permissions, or if you don't have the right resources provisioned
    if response.status_code == 200:
        # If the request was successful, we call another function to now retrieve Genie's response to our question
        return get_genie_message(space_id, response.json()['conversation_id'], response.json()['message_id'], token, databricks_host)
    else:
        raise Exception(f"API request failed at start_conversation: {response.status_code}, {response.text}")

# Function for retrieving Genie's response to the message we sent     
def get_genie_message(space_id, conversation_id, message_id, token, databricks_host):
    # First, we check that the access token is valid
    token = is_token_valid(token)

    # Then, we make an API request to the Genie space 
    url = f"https://{databricks_host}/api/2.0/genie/spaces/{space_id}/conversations/{conversation_id}/messages/{message_id}"

    headers = {
        "Authorization": f"Bearer {token['access_token']}"
    }

    response = requests.get(url, headers=headers)

    # Finally, we check the response to see if the API call was succesful
    if response.status_code == 200:
      # After verifying that the request was succesful, we need to keep polling the endpoint until Genie finishes generating its response
      while True:
        response = requests.get(url, headers=headers).json()
        state = response['status']

        # In this stage, Genie finished generating a response and we can now check the content that Genie generated
        if state == 'COMPLETED':
          print(f"Generation complete.")
          # If the response only contains text, retrieve the text (In some cases, Genie's response will also contain data)
          if 'text' in response['attachments'][0]:
            return {'message_id': message_id,
                    'conversation_id': conversation_id,
                    'attachment_id': response['attachments'][0]['attachment_id'],
                    'content':response['attachments'][0]['text']['content']}
          # If the response also contains a query, we need to call another API endpoint to retrieve the query results
          elif 'query' in response['attachments'][0]:
            attachment_id = response['attachments'][0]['attachment_id']
            #query_result = get_genie_message_query_result(space_id, conversation_id, message_id, token, databricks_host)
            query_result = get_genie_message_query_result_updated(space_id, conversation_id, message_id, attachment_id, token, databricks_host)
            return {'message_id':message_id,
                    'conversation_id':conversation_id,
                    'attachment_id': response['attachments'][0]['attachment_id'],
                    'description':response['attachments'][0]['query']['description'],
                    'query_result':query_result}
        # In this stage, Genie is still generating a response
        elif state in ["SUBMITTED",'FILTERING_CONTEXT','FETCHING_METADATA','ASKING_AI','PENDING_WAREHOUSE']:
          print(f"Generation in progress: {state}")
          time.sleep(3)
        # In this stage, the SQL query is still executing
        elif state == 'EXECUTING_QUERY':
          print(f"Query execution in progress: {state}")
          time.sleep(3)
        # In this stage, the generation failed
        elif state == 'FAILED':
          raise Exception(f"API request failed: {response['error']}")
        else:
          print(f"No query result: {state}")
          return None
    else:
      raise Exception(f"API request failed at get_message: {response.status_code}, {response.text}")
    
# Function for retrieving the query result for the SQL query that Genie executed   
def get_genie_message_query_result(space_id, conversation_id, message_id, token, databricks_host):
    token = is_token_valid(token)
    # Construct the URL
    url = f"https://{databricks_host}/api/2.0/genie/spaces/{space_id}/conversations/{conversation_id}/messages/{message_id}/query-result"

    # Set up the headers
    headers = {
        "Authorization": f"Bearer {token['access_token']}"
    }

    # Make the GET request
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        while True:
            response = requests.get(url, headers=headers).json()['statement_response']
            state = response['status']['state']
            if state == 'SUCCEEDED':
                data = response.get('result', {})
                meta = response['manifest']
                print("Successfully retrieved query result.")

                columns = [c['name'] for c in meta['schema']['columns']]

                if data and 'data_typed_array' in data:
                    # Check if the values in data_typed_array are not empty
                    if any(value for row in data['data_typed_array'] for value in row['values']):
                        rows = [[c.get('str', '') for c in r['values']] for r in data['data_typed_array']]
                        df = pd.DataFrame(rows, columns=columns)

                        # Handle duplicate column names
                        if df.columns.duplicated().any():
                            df.columns = [
                                f"{col}_{i}" if is_duplicate else col
                                for i, (col, is_duplicate) in enumerate(zip(df.columns, df.columns.duplicated()), 1)
                            ]

                    else:
                        df = pd.DataFrame()
                else:
                    df = pd.DataFrame()

                return df.to_json(orient='records')            
            elif state == 'RUNNING' or state == 'PENDING':
                print(f"Waiting for query result...")
                time.sleep(5)
            else:
                print(f"No query result: {response['state']}")
                return None
    else:
        raise Exception(f"API request failed at get_query_results: {response.status_code}, {response.text}")

# Function for retrieving the query result for the SQL query that Genie executed 
def get_genie_message_query_result_updated(space_id, conversation_id, message_id, attachment_id, token, databricks_host):
    # First, we check that the access token is valid
    token = is_token_valid(token)

    # Then, we make an API request to the Genie space 
    url = f"https://{databricks_host}/api/2.0//genie/spaces/{space_id}/conversations/{conversation_id}/messages/{message_id}/query-result/{attachment_id}"

    headers = {
        "Authorization": f"Bearer {token['access_token']}"
    }

    response = requests.get(url, headers=headers)
    print(response.json()) # DELETE LATER

    # Finally, we check the response to see if the API call was succesful
    if response.status_code == 200:
        while True:
            # The payload is wrapped inside a "statement_response" key, so we are going to unwrap it and store in as a response.
            #response = requests.get(url, headers=headers).json()['statement_response']
            try:
               response = requests.get(url, headers=headers).json()['statement_response']
            except:
               response = requests.get(url, headers=headers).json()

            # We also extract the status of the SQL query execution
            state = response['status']['state']
            # In this stage, the SQL Query finished running. We now package the data into a pandas dataframe and return it to the front-end.
            if state == 'SUCCEEDED': 
                # "Results" stores the actual data.
                # Sometimes, when there is no data available, this response is empty.
                data = response.get('result', {})
                rows = data.get('data_array',[])

                # "Meta" stores metadata about the query results, including the column names.
                meta = response['manifest']
                columns = [column['name'] for column in meta['schema']['columns']] 

                # Sanity Check
                print("Successfully retrieved query result.")

                # If empty rows are returned, create a dataframe with "No Data Available"
                if rows == []:
                    df = pd.DataFrame([{"Message": "No data available"}])
                else:
                    # Package data into a Pandas Dataframe.
                    df = pd.DataFrame(rows, columns=columns)

                    # Some joins may result in duplicate columns, which Pandas doesn't like. Handle duplicate column names here.
                    if df.columns.duplicated().any():
                        df.columns = [
                            f"{col}_{i}" if is_duplicate else col
                            for i, (col, is_duplicate) in enumerate(zip(df.columns, df.columns.duplicated()), 1)
                        ]
                
                return df.to_json(orient='records')    
            # In this stage, the query is still executing so we retry after 5 seconds. We could also implement incremental back-off here.        
            elif state == 'RUNNING' or state == 'PENDING':
                print(f"Waiting for query result...")
                time.sleep(5)
            # Otherwise, raise an error
            else:
                print(f"Error getting Query Result: {response['state']}")
                return None
    else:
        raise Exception(f"API request failed at get_query_results: {response.status_code}, {response.text}")

# Function for asking a followup question to an existing conversation       
def continue_genie_conversation(space_id, content, conversation_id, token, databricks_host):
    # First, we check that the access token is valid
    token = is_token_valid(token)

    # Then, we make an API request to the Genie space 
    url = f"https://{databricks_host}/api/2.0/genie/spaces/{space_id}/conversations/{conversation_id}/messages"

    headers = {
        "Authorization": f"Bearer {token['access_token']}",
        "Content-Type": "application/json"
    }

    payload = {
        "content": content
    }

    response = requests.post(url, headers=headers, data=json.dumps(payload))

    # Finally, we check the response to see if the API call was succesful
    if response.status_code == 200:
        # If the request was successful, we call another function to now retrieve Genie's response to our question
        return get_genie_message(space_id, conversation_id, response.json()['message_id'], token, databricks_host)
    else:
        raise Exception(f"API request failed at create_message: {response.status_code}, {response.text}")