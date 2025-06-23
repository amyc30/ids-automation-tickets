from atlassian import Confluence
import re
from bs4 import BeautifulSoup
from colorama import init, Fore, Style
from tabulate import tabulate
import requests
import json
from main import get_user_details, extract_tagged_users  # Import the functions from main.py
from update_epic import *
from config import *

# Initialize colorama
init()

# Jira functions are now imported from update_epic module

def get_planned_epics():
    """
    Fetch and parse the table under "Planned for H2" from the Confluence page.
    """
    # Load existing epic data
    epic_data = load_epic_json()
    
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
    
    # Debug print all headers to see what we're working with
    print(f"\n{Fore.YELLOW}Debug - All Headers:{Style.RESET_ALL}")
    for header in soup.find_all(['h1', 'h2', 'h3']):
        print(f"Header level {header.name}: {header.get_text(strip=True)}")
    
    # Try different ways to find the header
    planned_header = None
    
    # Method 1: Direct h1 search
    planned_header = soup.find('h1', string=H2_PAGE_TABLE_HEADER)
    
    # Method 2: Case-insensitive search
    if not planned_header:
        planned_header = soup.find('h1', string=lambda text: text and H2_PAGE_TABLE_HEADER.lower() in text.lower())
    
    # Method 3: Partial match
    if not planned_header:
        planned_header = soup.find('h1', string=lambda text: text and 'planned' in text.lower())
    
    if not planned_header:
        print(f"{Fore.RED}Could not find '{H2_PAGE_TABLE_HEADER}' header{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Debug - HTML content around headers:{Style.RESET_ALL}")
        # Print some HTML content to help debug
        for header in soup.find_all(['h1', 'h2', 'h3']):
            print(f"\nHeader: {header}")
            print(f"Next element: {header.next_sibling}")
        return
    
    print(f"\n{Fore.GREEN}Found header: {planned_header.get_text(strip=True)}{Style.RESET_ALL}")
    
    # Find the next table after the header
    table = planned_header.find_next('table')
    if not table:
        print(f"{Fore.RED}Could not find table under '{H2_PAGE_TABLE_HEADER}' header{Style.RESET_ALL}")
        return
    
    # Extract table data
    headers = [th.get_text(strip=True) for th in table.find_all('th')]
    
    rows = []
    for row in table.find_all('tr')[1:]:  # Skip header row
        cells = []
        owner_account_id = None
        for i, td in enumerate(row.find_all('td')):
            if i == 4:  # Owner column (4th column)
                # Get the first user element for account ID
                user_element = td.find('ri:user')
                if user_element:
                    owner_account_id = user_element.get('ri:account-id')
                # Get display names for display
                users = extract_tagged_users(td, CONFLUENCE_URL, USERNAME, API_TOKEN)
                owner_text = ', '.join(users) if users else ''
                cells.append(owner_text)
            elif i == 3:  # Note column (5th column)
                cells.append(td.get_text(strip=True))
            else:
                cells.append(td.get_text(strip=True))
        if cells:
            # Add the owner account ID as the last element
            cells.append(owner_account_id)
            rows.append(cells)

    # Create Jira Epics for each row
    if rows:
        print(f"\n{Fore.YELLOW}Processing KP projects...{Style.RESET_ALL}")
        kp_count = 0
        updated = False
        
        # Get the table rows again to extract links
        table_rows = table.find_all('tr')[1:]  # Skip header row
        
        for i, row in enumerate(rows):
            # Check if the project title includes "KP"
            if "KP" in row[0]:
                print(f"\n{Fore.CYAN}Found KP project: {row[0]}{Style.RESET_ALL}")
                # create_jira_epic(row, dri_account_id)
                kp_count += 1
                
                # Extract page ID from the link in the corresponding table row
                project_page_id = None
                if i < len(table_rows):
                    table_row = table_rows[i]
                    # Find the link column (usually the last column with links)
                    link_cells = table_row.find_all('td')
                    print(f"{Fore.CYAN}Debug - Found {len(link_cells)} cells in row {i} for project: {row[0]}{Style.RESET_ALL}")
                    
                    # Try to find links in multiple columns, not just column 6
                    link_found = False
                    for col_idx in range(len(link_cells)):
                        link_cell = link_cells[col_idx]
                        link_element = link_cell.find('a')
                        if link_element:
                            link_url = link_element.get('href', '')
                            if link_url and ('confluence' in link_url.lower() or '/pages/' in link_url or 'pageId=' in link_url or '/wiki/x/' in link_url):
                                print(f"{Fore.CYAN}Debug - Found Confluence link in column {col_idx}: {link_url}{Style.RESET_ALL}")
                                project_page_id = extract_page_id_from_link(link_url, USERNAME, API_TOKEN)
                                link_found = True
                                break
                            else:
                                print(f"{Fore.YELLOW}Debug - Found non-Confluence link in column {col_idx}: {link_url}{Style.RESET_ALL}")
                    
                    if not link_found:
                        print(f"{Fore.YELLOW}No Confluence link found in any column for project: {row[0]}{Style.RESET_ALL}")
                        # Debug: show all cell contents
                        for col_idx, cell in enumerate(link_cells):
                            cell_text = cell.get_text(strip=True)
                            if cell_text:
                                print(f"{Fore.YELLOW}  Column {col_idx}: {cell_text[:50]}...{Style.RESET_ALL}")
                else:
                    print(f"{Fore.RED}Error: Could not find table row {i}{Style.RESET_ALL}")
                
                # Check if this project already exists in epic.json
                existing_entry = find_epic_entry(epic_data, row[0])
                
                if existing_entry:
                    print(f"{Fore.YELLOW}Project already exists in epic.json with Jira epic: {existing_entry.get('jira_epic_id', 'N/A')}{Style.RESET_ALL}")
                    print(f"  Current page ID: {existing_entry.get('confluence_page_id', 'None')}")
                    print(f"  Extracted page ID: {project_page_id}")
                    
                    # If page ID is missing (null) or different, update it
                    if not existing_entry.get('confluence_page_id') and project_page_id:
                        update_epic_entry(existing_entry, confluence_page_id=project_page_id)
                        updated = True
                        print(f"{Fore.GREEN}✓ Added missing page ID for {row[0]}: {project_page_id}{Style.RESET_ALL}")
                    elif project_page_id and existing_entry.get('confluence_page_id') != project_page_id:
                        # Update confluence_page_id if it's different
                        update_epic_entry(existing_entry, confluence_page_id=project_page_id)
                        updated = True
                        print(f"{Fore.YELLOW}✓ Updated confluence page ID for {row[0]} from {existing_entry.get('confluence_page_id')} to {project_page_id}{Style.RESET_ALL}")
                    elif not project_page_id:
                        print(f"{Fore.RED}⚠ Could not extract page ID for {row[0]}{Style.RESET_ALL}")
                    
                    # Prepare project details for epic operations
                    details = {
                        'Project': row[0],
                        'Priority': row[2],
                        'Description': row[3],  # Note column
                        'Owner': row[4],  # Owner display name
                        'Owner Account ID': row[-1],  # Owner account ID (last element)
                        'Success Measures': row[5],  # Success measure(s)
                        'Link': row[6] if len(row) > 6 else 'No link'  # Link if available
                    }
                    
                    # Check if this project needs a Jira epic created (jira_epic_id is null)
                    if not existing_entry.get('jira_epic_id'):
                        print(f"{Fore.CYAN}Project exists but has no Jira epic yet. Creating epic for {row[0]}{Style.RESET_ALL}")
                        
                        print(f"\n{Fore.CYAN}KP Project Details:{Style.RESET_ALL}")
                        print(f"Project: {details['Project']}")
                        print(f"Priority: {details['Priority']}")
                        print(f"Description: {details['Description']}")
                        print(f"Owner: {details['Owner']}")
                        print(f"Owner Account ID: {details['Owner Account ID']}")
                        print(f"Success Measures: {details['Success Measures']}")
                        print(f"Link: {details['Link']}")
                        print("-" * 50)
                        
                        # Create Jira Epic for this project
                        ticket = create_jira_epic(details, details['Owner Account ID'], JIRA_URL, USERNAME, API_TOKEN, JIRA_PROJECT)
                        
                        if ticket:
                            # Update existing entry with the new epic ID
                            update_epic_entry(existing_entry, jira_epic_id=ticket['key'])
                            updated = True
                            print(f"{Fore.GREEN}Created epic {ticket['key']} for {row[0]}{Style.RESET_ALL}")
                        else:
                            print(f"{Fore.RED}Failed to create epic for {row[0]}{Style.RESET_ALL}")
                    else:
                        # Epic exists, update it with new data from the table
                        print(f"{Fore.CYAN}Updating existing epic {existing_entry.get('jira_epic_id')} for {row[0]}{Style.RESET_ALL}")
                        
                        if update_jira_epic(existing_entry.get('jira_epic_id'), details, JIRA_URL, USERNAME, API_TOKEN):
                            print(f"{Fore.GREEN}Updated epic {existing_entry.get('jira_epic_id')} for {row[0]}{Style.RESET_ALL}")
                        else:
                            print(f"{Fore.RED}Failed to update epic {existing_entry.get('jira_epic_id')} for {row[0]}{Style.RESET_ALL}")
                else:
                    # Create new entry for this project - now processing ALL KP projects
                    print(f"\n{Fore.YELLOW}Debug - Row contents for {row[0]}:{Style.RESET_ALL}")
                    for idx, content in enumerate(row):
                        print(f"Index {idx}: {content}")
                    
                    details = {
                        'Project': row[0],
                        'Priority': row[2],
                        'Description': row[3],  # Note column
                        'Owner': row[4],  # Owner display name
                        'Owner Account ID': row[-1],  # Owner account ID (last element)
                        'Success Measures': row[5],  # Success measure(s)
                        'Link': row[6] if len(row) > 6 else 'No link'  # Link if available
                    }
                    
                    print(f"\n{Fore.CYAN}KP Project Details:{Style.RESET_ALL}")
                    print(f"\n{Fore.YELLOW}Project: {details['Project']}{Style.RESET_ALL}")
                    print(f"Priority: {details['Priority']}")
                    print(f"Description: {details['Description']}")
                    print(f"Owner: {details['Owner']}")
                    print(f"Owner Account ID: {details['Owner Account ID']}")
                    print(f"Success Measures: {details['Success Measures']}")
                    print(f"Link: {details['Link']}")
                    print("-" * 50)
                    
                    # Create Jira Epic for this project
                    ticket = create_jira_epic(details, details['Owner Account ID'], JIRA_URL, USERNAME, API_TOKEN, JIRA_PROJECT)
                    
                    if ticket:
                        # Add new entry to epic_data using the extracted page ID
                        add_epic_entry(epic_data, row[0], project_page_id, ticket['key'])
                        updated = True
                        print(f"{Fore.GREEN}Added {row[0]} to epic.json with page ID {project_page_id}{Style.RESET_ALL}")
                    else:
                        # If epic creation failed, still add to JSON without epic ID
                        add_epic_entry(epic_data, row[0], project_page_id)
                        updated = True
                        print(f"{Fore.YELLOW}Added {row[0]} to epic.json (epic creation failed) with page ID {project_page_id}{Style.RESET_ALL}")
            else:
                print(f"DEBUG: Skipped: '{row[0]}'")
        
        print(f"\n{Fore.GREEN}Total KP projects found: {kp_count}{Style.RESET_ALL}")
        
        # Save updated epic.json if there were changes
        if updated:
            save_epic_json(epic_data)
        else:
            print(f"{Fore.YELLOW}No changes to epic.json{Style.RESET_ALL}")
    else:
        print(f"{Fore.RED}No projects found in the table.{Style.RESET_ALL}")

def main():
    """
    Main function to fetch and create Epics from the Planned for H2 table.
    """
    # Validate configuration
    is_valid, missing_vars = validate_config()
    if not is_valid:
        print(f"{Fore.RED}Error: Missing required environment variables:{Style.RESET_ALL}")
        for var in missing_vars:
            print(f"{Fore.YELLOW}- {var}{Style.RESET_ALL}")
        print(f"\n{Fore.YELLOW}Please ensure all required variables are set in your .env file{Style.RESET_ALL}")
        return

    print(f"{Fore.GREEN}Fetching table from Confluence page...{Style.RESET_ALL}")
    get_planned_epics()
    print(f"\n{Fore.GREEN}Done!{Style.RESET_ALL}")

if __name__ == "__main__":
    main()
