from atlassian import Confluence, Jira
import re
from bs4 import BeautifulSoup
import os
from dotenv import load_dotenv
from colorama import init, Fore, Style
from tabulate import tabulate
import requests
import json

# Initialize colorama
init()

# Load environment variables
load_dotenv()

# Configuration variables from .env
CONFLUENCE_URL = os.getenv('CONFLUENCE_URL')
JIRA_URL = os.getenv('CONFLUENCE_URL')  # Using same URL for Jira
USERNAME = os.getenv('CONFLUENCE_USERNAME')
API_TOKEN = os.getenv('CONFLUENCE_API_TOKEN')
PAGE_ID = os.getenv('CONFLUENCE_PAGE_ID')

# Jira configuration
JIRA_PROJECT = "IDS"  # Your project key
ISSUE_TYPE = "Task"

def create_jira_ticket(task_data, reporter_account_id):
    # Initialize Jira client
    jira = Jira(
        url=JIRA_URL,
        username=USERNAME,
        password=API_TOKEN
    )

    # Map effort levels to story points
    effort_map = {
        "SMALL (1-3 DAYS)": 2,
        "MEDIUM (1-2 WEEKS)": 5,
        "LARGE (3+ WEEKS)": 8
    }

    # Get the owner account ID from the table (last element)
    assignee_account_id = task_data[-1]  # The account ID we stored at the end of the cells

    # Debug print for task data
    print(f"\n{Fore.YELLOW}Debug - Task Data:{Style.RESET_ALL}")
    print(f"Title: {task_data[0]}")
    print(f"Priority: {task_data[1].replace('Red', '').replace('Yellow', '').replace('Green', '')}")
    print(f"Level of Effort: {task_data[2]}")
    print(f"Owner: {task_data[3]}")
    print(f"Owner Account ID: {assignee_account_id}")
    print(f"Note: {task_data[4]}")

    # Clean up effort text and get story points
    effort_text = task_data[2].replace('Red', '').replace('Yellow', '').strip()
    story_points = effort_map.get(effort_text, 3)  # Default to 3 if not found

    # Create issue data
    issue_data = {
        "fields": {
            "project": {"key": JIRA_PROJECT},
            "summary": task_data[0],  # Task title
            "description": f'''
*Note from Confluence:*
{task_data[4]}
            ''',
            "issuetype": {"name": ISSUE_TYPE},
            "priority": {"name": task_data[1].replace('Red', '').replace('Yellow', '')},  # Just clean the priority text
            "assignee": {"id": assignee_account_id},  # Use the account ID for assignee
            "reporter": {"id": reporter_account_id}  # Use the account ID for reporter
        }
    }

    # Debug print the complete issue data
    print(f"\n{Fore.YELLOW}Debug - Issue Data:{Style.RESET_ALL}")
    print(json.dumps(issue_data, indent=2))

    try:
        # Create the issue
        ticket = jira.issue_create(fields=issue_data["fields"])
        print(f"{Fore.GREEN}Successfully created Jira ticket: {ticket['key']}{Style.RESET_ALL}")
        print(f"Title: {task_data[0]}")
        print(f"Priority: {task_data[1]}")
        print(f"Story Points: {story_points}")
        print(f"Assignee: {task_data[3]}")
        return ticket
    except Exception as e:
        print(f"{Fore.RED}Failed to create Jira ticket: {str(e)}{Style.RESET_ALL}")
        return None

def get_user_details(account_id, confluence_url, username, api_token):
    """
    Get user details using direct REST API call.
    """
    # Construct the API URL - using the correct Confluence API endpoint
    api_url = f"{confluence_url}/wiki/rest/api/user"
    params = {'accountId': account_id}  # Use the complete account ID
    
    # Make the API request
    response = requests.get(
        api_url,
        params=params,
        auth=(username, api_token),
        headers={'Accept': 'application/json'}
    )
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"{Fore.RED}API request failed with status {response.status_code}: {response.text}{Style.RESET_ALL}")
        return None

def extract_tagged_users(cell, confluence_url, username, api_token):
    """
    Extract tagged users from a Confluence cell and get their display names.
    """
    users = []
    
    # Find all user elements
    user_elements = cell.find_all('ri:user')
    
    for user in user_elements:
        # Get the account ID
        account_id = user.get('ri:account-id')
        
        if account_id:
            try:
                # Get user details using direct API call
                user_details = get_user_details(account_id, confluence_url, username, api_token)
                
                if user_details and 'displayName' in user_details:
                    display_name = user_details['displayName']
                    users.append(display_name)
                else:
                    # Fallback to account ID if display name not found
                    fallback_id = account_id.split(':')[-1]
                    users.append(fallback_id)
            except Exception as e:
                print(f"{Fore.RED}Error fetching user details: {str(e)}{Style.RESET_ALL}")
                # Fallback to account ID if API call fails
                fallback_id = account_id.split(':')[-1]
                print(f"Using fallback ID due to error: {fallback_id}")
                users.append(fallback_id)
    
    return users

def get_scope_table():
    """
    Fetch and parse the table under the Scope header from the Confluence page.
    """
    # Initialize Confluence client
    confluence = Confluence(
        url=CONFLUENCE_URL,
        username=USERNAME,
        password=API_TOKEN
    )

    # Get page content
    page_content = confluence.get_page_by_id(page_id=PAGE_ID, expand="body.storage")
    if not page_content:
        print(f"{Fore.RED}Failed to fetch Confluence page content.{Style.RESET_ALL}")
        return

    # Get the HTML content
    html_content = page_content.get('body', {}).get('storage', {}).get('value', '')
    
    # Parse HTML with BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Find the DRI line
    dri = None
    dri_account_id = None
    for p in soup.find_all('p'):
        text = p.get_text(strip=True)
        if text.startswith('DRI:'):
            # Find the user element to get account ID
            user_element = p.find('ri:user')
            if user_element:
                dri_account_id = user_element.get('ri:account-id')
                # Get display name for debug
                users = extract_tagged_users(p, CONFLUENCE_URL, USERNAME, API_TOKEN)
                if users:
                    print(f"\n{Fore.YELLOW}Debug - DRI/Reporter:{Style.RESET_ALL}")
                    print(f"Original: {users[0]}")
                    print(f"Account ID: {dri_account_id}")
                break
    
    # Find the Scope header
    scope_header = soup.find('h1', string='Scope')
    if not scope_header:
        print(f"{Fore.RED}Could not find 'Scope' header{Style.RESET_ALL}")
        return
    
    # Find the next table after the Scope header
    table = scope_header.find_next('table')
    if not table:
        print(f"{Fore.RED}Could not find table under 'Scope' header{Style.RESET_ALL}")
        return
    
    # Extract table data
    headers = [th.get_text(strip=True) for th in table.find_all('th')]
    print(f"\n{Fore.YELLOW}Debug - Headers:{Style.RESET_ALL}")
    print(headers)
    
    rows = []
    for row in table.find_all('tr')[1:]:  # Skip header row
        cells = []
        owner_account_id = None
        for i, td in enumerate(row.find_all('td')):
            if i == 3:  # Owner column (4th column)
                # Get the first user element for account ID
                user_element = td.find('ri:user')
                if user_element:
                    owner_account_id = user_element.get('ri:account-id')
                # Get display names for display
                users = extract_tagged_users(td, CONFLUENCE_URL, USERNAME, API_TOKEN)
                owner_text = ', '.join(users) if users else ''
                cells.append(owner_text)
            elif i == 4:  # Note column (5th column)
                cells.append(td.get_text(strip=True))
            else:
                cells.append(td.get_text(strip=True))
        if cells:
            # Add the owner account ID as the last element
            cells.append(owner_account_id)
            rows.append(cells)
    
    # Print the table with formatting
    print(f"\n{Fore.CYAN}Table under Scope header:{Style.RESET_ALL}")
    # Create a copy of rows without the account ID for display
    display_rows = [row[:-1] for row in rows] if rows and len(rows[0]) > 5 else rows
    print(tabulate(display_rows, headers=headers, tablefmt="grid"))

    # Create Jira ticket for the first row
    if rows:
        print(f"\n{Fore.YELLOW}Creating Jira ticket for first task...{Style.RESET_ALL}")
        create_jira_ticket(rows[0], dri_account_id)  # Pass the DRI account ID to create_jira_ticket
    else:
        print(f"{Fore.RED}No tasks found in the table.{Style.RESET_ALL}")

def main():
    """
    Main function to fetch and display the Scope table.
    """
    # Validate environment variables
    required_vars = ['CONFLUENCE_URL', 'CONFLUENCE_USERNAME', 'CONFLUENCE_API_TOKEN', 'CONFLUENCE_PAGE_ID']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"{Fore.RED}Error: Missing required environment variables:{Style.RESET_ALL}")
        for var in missing_vars:
            print(f"{Fore.YELLOW}- {var}{Style.RESET_ALL}")
        print(f"\n{Fore.YELLOW}Please ensure all required variables are set in your .env file{Style.RESET_ALL}")
        return

    print(f"{Fore.GREEN}Fetching table from Confluence page...{Style.RESET_ALL}")
    get_scope_table()
    print(f"\n{Fore.GREEN}Done!{Style.RESET_ALL}")

if __name__ == "__main__":
    main()
