import json
import os
import re
import requests
from colorama import Fore, Style
from atlassian import Jira

def resolve_shortened_confluence_url(short_url, username, api_token):
    """
    Resolve a shortened Confluence URL to get the actual page ID.
    """
    try:
        print(f"{Fore.CYAN}Debug - Resolving shortened URL: {short_url}{Style.RESET_ALL}")
        
        # First try to extract page ID directly from the URL if it's already in a recognizable format
        direct_page_id = extract_page_id_from_resolved_url(short_url)
        if direct_page_id:
            print(f"{Fore.GREEN}Debug - Extracted page ID {direct_page_id} directly from URL without HTTP request{Style.RESET_ALL}")
            return direct_page_id
        
        # Make a HEAD request to follow redirects without downloading content
        response = requests.head(
            short_url,
            auth=(username, api_token),
            allow_redirects=True,
            timeout=10
        )
        
        # Check if we got a redirect or if the final URL is different
        final_url = response.url
        if final_url != short_url:
            print(f"{Fore.CYAN}Debug - URL redirected to: {final_url}{Style.RESET_ALL}")
            # Try to extract page ID from the redirected URL
            page_id = extract_page_id_from_resolved_url(final_url)
            if page_id:
                return page_id
        
        # Even if we get an error status, try to extract from the final URL
        if response.status_code in [200, 302, 401, 403]:  # Include auth errors as they might still have valid redirects
            final_url = response.url
            print(f"{Fore.CYAN}Debug - Final URL (status {response.status_code}): {final_url}{Style.RESET_ALL}")
            
            # Now try to extract page ID from the resolved URL
            return extract_page_id_from_resolved_url(final_url)
        else:
            print(f"{Fore.YELLOW}Warning: Could not resolve shortened URL {short_url}, status: {response.status_code}{Style.RESET_ALL}")
            return None
            
    except Exception as e:
        print(f"{Fore.YELLOW}Warning: Error resolving shortened URL {short_url}: {str(e)}{Style.RESET_ALL}")
        # As a fallback, try to extract page ID directly from the original URL
        return extract_page_id_from_resolved_url(short_url)

def extract_page_id_from_resolved_url(url):
    """
    Extract page ID from a resolved Confluence URL.
    """
    patterns = [
        (r'/pages/(\d+)/', 'pages format'),
        (r'pageId=(\d+)', 'pageId parameter'),
        (r'/wiki/spaces/[^/]+/pages/(\d+)/', 'wiki spaces format'),
        (r'/wiki/spaces/[^/]+/pages/(\d+)/[^/]*', 'wiki spaces with title format'),  # Handle URLs with page titles
        (r'/display/[^/]+/(\d+)', 'display format'),
        (r'/(\d{6,})(?:/|$)', 'standalone ID'),
        (r'(\d{6,})$', 'ending with ID'),
    ]
    
    for pattern, description in patterns:
        match = re.search(pattern, url)
        if match:
            page_id = match.group(1)
            print(f"{Fore.GREEN}Debug - Extracted page ID {page_id} from resolved URL using {description} pattern{Style.RESET_ALL}")
            return page_id
    
    return None

def extract_page_id_from_link(link_text, username=None, api_token=None):
    """
    Extract Confluence page ID from a link.
    Handles various Confluence URL formats.
    """
    if not link_text or link_text == 'No link':
        return None
    
    print(f"{Fore.CYAN}Debug - Processing link: {link_text}{Style.RESET_ALL}")
    
    # Common Confluence URL patterns (ordered by specificity)
    patterns = [
        (r'/pages/(\d+)/', 'pages format'),  # /pages/123456/
        (r'pageId=(\d+)', 'pageId parameter'),   # pageId=123456
        (r'/wiki/spaces/[^/]+/pages/(\d+)/', 'wiki spaces format'),  # /wiki/spaces/SPACE/pages/123456/
        (r'/wiki/spaces/[^/]+/pages/(\d+)/[^/]*', 'wiki spaces with title format'),  # /wiki/spaces/SPACE/pages/123456/Page+Title
        (r'/display/[^/]+/(\d+)', 'display format'),  # /display/SPACE/123456
        (r'/(\d{6,})(?:/|$)', 'standalone ID'),  # /123456/ or /123456 (6+ digits to avoid false matches)
        (r'(\d{6,})$', 'ending with ID'),  # ending with 123456 (6+ digits)
        (r'/wiki/x/([A-Za-z0-9]+)', 'shortened wiki format'),  # /wiki/x/BwB4NAE (Confluence shortened URLs)
    ]
    
    for pattern, description in patterns:
        match = re.search(pattern, link_text)
        if match:
            page_id = match.group(1)
            
            # Handle shortened URLs - they need to be resolved
            if description == 'shortened wiki format':
                if username and api_token:
                    resolved_id = resolve_shortened_confluence_url(link_text, username, api_token)
                    if resolved_id:
                        return resolved_id
                    else:
                        print(f"{Fore.YELLOW}Warning: Could not resolve shortened URL, using encoded ID: {page_id}{Style.RESET_ALL}")
                        return page_id  # Return the encoded ID as fallback
                else:
                    print(f"{Fore.YELLOW}Warning: Cannot resolve shortened URL without credentials, using encoded ID: {page_id}{Style.RESET_ALL}")
                    return page_id  # Return the encoded ID as fallback
            else:
                print(f"{Fore.GREEN}Debug - Extracted page ID {page_id} using {description} pattern{Style.RESET_ALL}")
                return page_id
    
    print(f"{Fore.YELLOW}Warning: Could not extract page ID from link: {link_text}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}Debug - Link length: {len(link_text)}, starts with: {link_text[:50]}...{Style.RESET_ALL}")
    return None

def load_epic_json():
    """Load existing epic.json file or create empty structure"""
    try:
        with open('epic.json', 'r') as f:
            data = json.load(f)
            # Validate format - should be array of dictionaries
            if isinstance(data, list) and all(isinstance(item, dict) for item in data):
                return data
            else:
                print(f"{Fore.YELLOW}Warning: epic.json has incorrect format, creating new one{Style.RESET_ALL}")
                return []
    except FileNotFoundError:
        print(f"{Fore.YELLOW}epic.json not found, will create new one{Style.RESET_ALL}")
        return []
    except json.JSONDecodeError:
        print(f"{Fore.YELLOW}Warning: epic.json is corrupted, creating new one{Style.RESET_ALL}")
        return []

def save_epic_json(data):
    """Save data to epic.json file"""
    with open('epic.json', 'w') as f:
        json.dump(data, f, indent=2)
    print(f"{Fore.GREEN}Updated epic.json with {len(data)} entries{Style.RESET_ALL}")

def find_epic_entry(epic_data, project_name):
    """Find existing entry for a project"""
    for entry in epic_data:
        if entry.get('project_name') == project_name:
            return entry
    return None

def add_epic_entry(epic_data, project_name, confluence_page_id, jira_epic_id=None):
    """Add a new entry to epic data"""
    new_entry = {
        "project_name": project_name,
        "confluence_page_id": confluence_page_id,
        "jira_epic_id": jira_epic_id
    }
    epic_data.append(new_entry)
    return new_entry

def update_epic_entry(entry, confluence_page_id=None, jira_epic_id=None):
    """Update an existing epic entry"""
    updated = False
    if confluence_page_id and entry.get('confluence_page_id') != confluence_page_id:
        entry['confluence_page_id'] = confluence_page_id
        updated = True
    if jira_epic_id and entry.get('jira_epic_id') != jira_epic_id:
        entry['jira_epic_id'] = jira_epic_id
        updated = True
    return updated

def get_jira_client(jira_url, username, api_token):
    """Get a configured Jira client"""
    return Jira(
        url=jira_url,
        username=username,
        password=api_token
    )

def create_jira_epic(task_data, reporter_account_id, jira_url, username, api_token, jira_project):
    """Create a new Jira epic"""
    jira = get_jira_client(jira_url, username, api_token)

    if not reporter_account_id:
        print(f"{Fore.RED}Error: Reporter account ID is required but was not provided.{Style.RESET_ALL}")
        return None

    # Create issue data
    issue_data = {
        "fields": {
            "project": {"key": jira_project},
            "summary": task_data['Project'],  # Epic title
            "description": f'''
{task_data['Description']}

*Success Measures:*
{task_data['Success Measures']}

*Link to PRD:*
{task_data['Link']}
            ''',
            "issuetype": {"name": "Epic"},
            "priority": {"name": task_data['Priority'].replace('Red', '').replace('Yellow', '')},  # Clean the priority text
            "assignee": {"id": task_data['Owner Account ID']},  # Use the owner's account ID for assignee
            "reporter": {"id": reporter_account_id},  # Use the account ID for reporter
            "labels": ["ids-automation"],  # Add label for automation tracking
            "components": [{"name": "IDS Internal"}]  # Add component
        }
    }

    try:
        # Create the issue
        ticket = jira.issue_create(fields=issue_data["fields"])
        print(f"{Fore.GREEN}Successfully created Jira Epic: {ticket['key']}{Style.RESET_ALL}")
        print(f"Title: {task_data['Project']}")
        print(f"Priority: {task_data['Priority']}")
        print(f"Assignee: {task_data['Owner']}")
        print(f"Reporter Account ID: {reporter_account_id}")
        print(f"Labels: {', '.join(issue_data['fields']['labels'])}")
        print(f"Components: {', '.join(c['name'] for c in issue_data['fields']['components'])}")
        return ticket
    except Exception as e:
        print(f"{Fore.RED}Failed to create Jira Epic: {str(e)}{Style.RESET_ALL}")
        return None

def update_jira_epic(epic_key, task_data, jira_url, username, api_token):
    """Update an existing Jira epic with new data"""
    jira = get_jira_client(jira_url, username, api_token)

    # Prepare update data
    update_data = {
        "fields": {
            "summary": task_data['Project'],  # Epic title
            "description": f'''
{task_data['Description']}

*Success Measures:*
{task_data['Success Measures']}

*Link to PRD:*
{task_data['Link']}
            ''',
            "priority": {"name": task_data['Priority'].replace('Red', '').replace('Yellow', '')},  # Clean the priority text
            "assignee": {"id": task_data['Owner Account ID']},  # Use the owner's account ID for assignee
        }
    }

    try:
        # Update the issue
        jira.issue_update(issue_key=epic_key, fields=update_data["fields"])
        print(f"{Fore.GREEN}Successfully updated Jira Epic: {epic_key}{Style.RESET_ALL}")
        print(f"Title: {task_data['Project']}")
        print(f"Priority: {task_data['Priority']}")
        print(f"Assignee: {task_data['Owner']}")
        return True
    except Exception as e:
        print(f"{Fore.RED}Failed to update Jira Epic {epic_key}: {str(e)}{Style.RESET_ALL}")
        return False