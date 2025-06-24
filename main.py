from atlassian import Confluence, Jira
import re
from bs4 import BeautifulSoup
from colorama import init, Fore, Style
from tabulate import tabulate
import requests
import json
import sys
from config import *

# Initialize colorama
init()

# Use the main.py specific variables
ISSUE_TYPE = TASK_ISSUE_TYPE

def create_jira_ticket(task_data, reporter_account_id, epic_key):
    # Validate task data has required fields
    try:
        if len(task_data) < 6:
            print(f"{Fore.RED}Error: Incomplete task data - need at least 6 fields, got {len(task_data)}{Style.RESET_ALL}")
            return None
            
        # Check for required fields
        if not task_data[0] or not task_data[0].strip():
            print(f"{Fore.RED}Error: Task title is empty or missing{Style.RESET_ALL}")
            return None
            
    except (IndexError, TypeError) as e:
        print(f"{Fore.RED}Error: Invalid task data structure: {str(e)}{Style.RESET_ALL}")
        return None
    
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

    try:
        # Get the owner account ID from the table (last element)
        assignee_account_id = task_data[-1]  # The account ID we stored at the end of the cells

        # Debug print for task data
        print(f"\n{Fore.YELLOW}Debug - Task Data:{Style.RESET_ALL}")
        print(f"Title: {task_data[0]}")
        print(f"Priority (raw): {task_data[1] if len(task_data) > 1 else 'None'}")
        print(f"Level of Effort: {task_data[2] if len(task_data) > 2 else 'None'}")
        print(f"Owner: {task_data[3] if len(task_data) > 3 else 'None'}")
        print(f"Owner Account ID: {assignee_account_id}")
        print(f"Note: {task_data[4] if len(task_data) > 4 else 'None'}")

        # Clean up effort text and get story points
        effort_text = (task_data[2] if len(task_data) > 2 and task_data[2] else "").replace('Red', '').replace('Yellow', '').replace('Green', '').replace('Blue', '').strip()
        story_points = effort_map.get(effort_text, 3)  # Default to 3 if not found
        
    except (IndexError, TypeError) as e:
        print(f"{Fore.RED}Error processing task data: {str(e)}{Style.RESET_ALL}")
        return None

    # Create issue data with safe field access
    try:
        # Process priority - only set if there's a valid value from the table
        priority_text = None
        if len(task_data) > 1 and task_data[1] and task_data[1].strip():
            priority_text = task_data[1].replace('Red', '').replace('Yellow', '').replace('Green', '').replace('Blue', '').strip()
            if not priority_text:  # If after cleaning it's empty, don't set priority
                priority_text = None
            
        note_text = task_data[4] if len(task_data) > 4 and task_data[4] else "No additional notes"
        
        issue_data = {
            "fields": {
                "project": {"key": JIRA_PROJECT},
                "summary": task_data[0],  # Task title (already validated above)
                "description": f'''
*Note from Confluence:*
{note_text}
                ''',
                "issuetype": {"name": ISSUE_TYPE},
                "assignee": {"id": assignee_account_id},
                "reporter": {"id": reporter_account_id},
                "labels": ["ids-automation"],
                "components": [{"name": "IDS Internal"}]
            }
        }
        
        # Only add priority field if we have a valid priority value
        if priority_text:
            issue_data["fields"]["priority"] = {"name": priority_text}
    except (IndexError, TypeError) as e:
        print(f"{Fore.RED}Error creating issue data: {str(e)}{Style.RESET_ALL}")
        return None
    
    # Link to epic if provided
    if epic_key:
        issue_data["fields"]["parent"] = {"key": epic_key}
        print(f"{Fore.CYAN}Linking ticket to epic: {epic_key}{Style.RESET_ALL}")

    # Debug print the complete issue data
    print(f"\n{Fore.YELLOW}Debug - Issue Data:{Style.RESET_ALL}")
    print(json.dumps(issue_data, indent=2))

    try:
        # Create the issue
        ticket = jira.issue_create(fields=issue_data["fields"])
        print(f"{Fore.GREEN}Successfully created Jira ticket: {ticket['key']}{Style.RESET_ALL}")
        print(f"Title: {task_data[0]}")
        print(f"Priority: {priority_text if priority_text else 'Not set (will use Jira default)'}")
        print(f"Story Points: {story_points}")
        print(f"Assignee: {task_data[3]}")
        print(f"Labels: {', '.join(issue_data['fields']['labels'])}")
        print(f"Components: {', '.join(c['name'] for c in issue_data['fields']['components'])}")
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

def get_scope_table(page_id, create_tickets=True):
    """
    Fetch and parse the table under the Scope header from the Confluence page.
    Args:
        page_id: The Confluence page ID to process
        create_tickets: If True, create tickets; if False, just return the data
    Returns:
        If create_tickets=False: (rows, dri_account_id) tuple
        If create_tickets=True: None (creates tickets directly)
    """
    # Initialize Confluence client
    confluence = Confluence(
        url=CONFLUENCE_URL,
        username=USERNAME,
        password=API_TOKEN
    )

    # Get page content
    page_content = confluence.get_page_by_id(page_id=page_id, expand="body.storage")
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
    scope_header = soup.find('h1', string=PRD_PAGE_TABLE_HEADER)
    if not scope_header:
        print(f"{Fore.RED}Could not find '{PRD_PAGE_TABLE_HEADER}' header{Style.RESET_ALL}")
        return
    
    # Find the next table after the Scope header
    table = scope_header.find_next('table')
    if not table:
        print(f"{Fore.RED}Could not find table under '{PRD_PAGE_TABLE_HEADER}' header{Style.RESET_ALL}")
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

    if create_tickets:
        # Create Jira ticket for the first row (original behavior)
        if rows:
            print(f"\n{Fore.YELLOW}Creating Jira ticket for first task...{Style.RESET_ALL}")
            create_jira_ticket(rows[0], dri_account_id, None)  # Pass None for epic_key since main.py doesn't link to epics
        else:
            print(f"{Fore.RED}No tasks found in the table.{Style.RESET_ALL}")
    else:
        # Return data for external processing
        return rows, dri_account_id

def main():
    """
    Main function to fetch and display the Scope table.
    Usage:
      python main.py <page_id>          # Direct mode - use specific page ID
    """
    
    # Show help if requested
    if handle_help_request([
        "python main.py <page_id>          # Process specific Confluence page ID",
        "",
        "This script processes a Confluence page and creates a Jira ticket from the first task"
    ]):
        return
    
    # Validate configuration
    if not handle_config_validation():
        return

    # Require page ID as command line argument
    if len(sys.argv) < 2:
        print(f"{Fore.RED}Error: Page ID is required{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Usage: python main.py <page_id>{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Use create_ticket.py for interactive page selection{Style.RESET_ALL}")
        return
    
    page_id = sys.argv[1]
    print(f"{Fore.CYAN}Processing page ID: {page_id}{Style.RESET_ALL}")
    
    print(f"{Fore.GREEN}Fetching table from Confluence page...{Style.RESET_ALL}")
    get_scope_table(page_id, create_tickets=True)
    print(f"\n{Fore.GREEN}Done!{Style.RESET_ALL}")

if __name__ == "__main__":
    main()
