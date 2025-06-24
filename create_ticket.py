import sys
from colorama import init, Fore, Style
from config import *
from update_epic import load_epic_json
from main import get_scope_table, create_jira_ticket

# Initialize colorama
init()

def get_available_pages():
    """
    Get available Confluence page IDs from epic.json
    """
    epic_data = load_epic_json()
    
    if not epic_data:
        print(f"{Fore.RED}No epic.json data found. Please run create_epic.py first.{Style.RESET_ALL}")
        return []
    
    # Get unique page IDs and project names
    pages = []
    for entry in epic_data:
        page_id = entry.get('confluence_page_id')
        project_name = entry.get('project_name')
        if page_id and project_name:
            pages.append({
                'page_id': page_id,
                'project_name': project_name,
                'jira_epic': entry.get('jira_epic_id', 'N/A')
            })
    
    return pages

def select_page_interactive():
    """
    Allow user to select which page to work with from epic.json
    Returns: page_id string, 'all' for all pages, or None for cancel
    """
    pages = get_available_pages()
    
    if not pages:
        print(f"{Fore.RED}No pages with valid page IDs found in epic.json{Style.RESET_ALL}")
        return None
    
    print(f"\n{Fore.CYAN}Available Confluence pages from epic.json:{Style.RESET_ALL}")
    for i, page in enumerate(pages, 1):
        print(f"{i}. {page['project_name']} (Page ID: {page['page_id']}) [Epic: {page['jira_epic']}]")
    
    print(f"{len(pages) + 1}. {Fore.MAGENTA}ALL PAGES - Process all pages with confirmation{Style.RESET_ALL}")
    
    try:
        choice = input(f"\n{Fore.YELLOW}Select a page number (1-{len(pages) + 1}): {Style.RESET_ALL}")
        index = int(choice) - 1
        
        if index == len(pages):  # User selected "ALL PAGES"
            print(f"{Fore.MAGENTA}Selected: Process all {len(pages)} pages{Style.RESET_ALL}")
            return 'all'
        elif 0 <= index < len(pages):
            selected_page = pages[index]
            print(f"{Fore.GREEN}Selected: {selected_page['project_name']} (Page ID: {selected_page['page_id']}){Style.RESET_ALL}")
            return selected_page['page_id']
        else:
            print(f"{Fore.RED}Invalid selection. Please choose a number between 1 and {len(pages) + 1}.{Style.RESET_ALL}")
            return None
    except (ValueError, KeyboardInterrupt):
        print(f"{Fore.RED}Invalid input or cancelled.{Style.RESET_ALL}")
        return None

def find_epic_for_page(page_id):
    """
    Find the epic key associated with a given Confluence page ID
    """
    epic_data = load_epic_json()
    
    for entry in epic_data:
        if entry.get('confluence_page_id') == str(page_id):
            epic_key = entry.get('jira_epic_id')
            if epic_key:
                print(f"{Fore.GREEN}Found epic {epic_key} for page {page_id}{Style.RESET_ALL}")
                return epic_key
            else:
                print(f"{Fore.YELLOW}Page {page_id} found in epic.json but no epic key set{Style.RESET_ALL}")
                return None
    
    print(f"{Fore.YELLOW}Page {page_id} not found in epic.json - tickets will not be linked to an epic{Style.RESET_ALL}")
    return None

def process_all_pages_with_confirmation():
    """
    Process all pages from epic.json with user confirmation for each page
    """
    pages = get_available_pages()
    
    if not pages:
        print(f"{Fore.RED}No pages found to process.{Style.RESET_ALL}")
        return
    
    print(f"\n{Fore.MAGENTA}Processing all {len(pages)} pages with confirmation...{Style.RESET_ALL}")
    
    total_successful = 0
    total_attempted = 0
    total_skipped = []
    pages_processed = 0
    
    for i, page in enumerate(pages, 1):
        print(f"\n{Fore.CYAN}{'='*80}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}Page {i}/{len(pages)}: {page['project_name']}{Style.RESET_ALL}")
        print(f"Page ID: {page['page_id']}")
        print(f"Epic: {page['jira_epic']}")
        print(f"{Fore.CYAN}{'='*80}{Style.RESET_ALL}")
        
        try:
            response = input(f"\n{Fore.YELLOW}Process this page? (y/n/q): {Style.RESET_ALL}").lower().strip()
            
            if response == 'q':
                print(f"{Fore.YELLOW}Quitting all pages processing.{Style.RESET_ALL}")
                break
            elif response == 'y':
                print(f"{Fore.GREEN}Processing page: {page['project_name']}{Style.RESET_ALL}")
                
                # Look up the epic for this page
                epic_key = find_epic_for_page(page['page_id'])
                
                # Get the table data from this page
                result = get_scope_table(page['page_id'], create_tickets=False)
                
                if result and len(result) == 2:
                    rows, dri_account_id = result
                    if rows:
                        print(f"{Fore.CYAN}Found {len(rows)} tasks on this page{Style.RESET_ALL}")
                        successful, attempted, skipped = process_tickets_interactively(rows, dri_account_id, epic_key)
                        total_successful += successful
                        total_attempted += attempted
                        total_skipped.extend(skipped)
                        pages_processed += 1
                    else:
                        print(f"{Fore.YELLOW}No tasks found on this page{Style.RESET_ALL}")
                        pages_processed += 1
                else:
                    print(f"{Fore.RED}Failed to extract table data from page {page['page_id']}{Style.RESET_ALL}")
                    pages_processed += 1
                    
            elif response == 'n':
                print(f"{Fore.YELLOW}Skipping page: {page['project_name']}{Style.RESET_ALL}")
            else:
                print(f"{Fore.YELLOW}Invalid response. Skipping page: {page['project_name']}{Style.RESET_ALL}")
                
        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}Process interrupted by user.{Style.RESET_ALL}")
            break
    
    # Print overall summary for all pages
    print(f"\n{Fore.MAGENTA}{'='*80}{Style.RESET_ALL}")
    print(f"{Fore.MAGENTA}OVERALL SUMMARY FOR ALL PAGES{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Pages processed: {pages_processed}/{len(pages)}{Style.RESET_ALL}")
    
    if total_attempted == 0:
        print(f"{Fore.YELLOW}No tickets were created across all pages{Style.RESET_ALL}")
    else:
        success_rate = (total_successful / total_attempted) * 100
        if total_successful == total_attempted:
            print(f"{Fore.GREEN}✓ {total_successful}/{total_attempted} tickets successfully created across all pages (100%){Style.RESET_ALL}")
        else:
            print(f"{Fore.YELLOW}✓ {total_successful}/{total_attempted} tickets successfully created across all pages ({success_rate:.1f}%){Style.RESET_ALL}")
            if total_successful < total_attempted:
                failed_count = total_attempted - total_successful
                print(f"{Fore.RED}✗ {failed_count} tickets failed to create{Style.RESET_ALL}")
    
    # Display skipped tickets summary
    if total_skipped:
        print(f"\n{Fore.YELLOW}SKIPPED TICKETS ({len(total_skipped)} total):{Style.RESET_ALL}")
        for skip_info in total_skipped:
            print(f"{Fore.YELLOW}  ✗ {skip_info['title']} - {skip_info['reason']}{Style.RESET_ALL}")
    
    print(f"{Fore.MAGENTA}{'='*80}{Style.RESET_ALL}")
    print(f"\n{Fore.GREEN}Finished processing all pages.{Style.RESET_ALL}")

def process_tickets_interactively(rows, dri_account_id, epic_key):
    """
    Process each row and create tickets automatically
    Returns: (successful_count, total_attempted_count, skipped_list)
    """
    if not rows:
        print(f"{Fore.RED}No tasks found in the table.{Style.RESET_ALL}")
        return 0, 0, []
    
    print(f"\n{Fore.CYAN}Found {len(rows)} tasks. Creating all tickets automatically...{Style.RESET_ALL}")
    if epic_key:
        print(f"{Fore.CYAN}All tickets will be linked to epic: {epic_key}{Style.RESET_ALL}")
    else:
        print(f"{Fore.YELLOW}No epic found - tickets will be created as standalone items{Style.RESET_ALL}")
    
    successful_count = 0
    total_attempted = 0
    skipped_tickets = []
    
    for i, row in enumerate(rows, 1):
        # Check if row has enough columns (need at least 5: title, priority, effort, owner, note, plus account_id)
        try:
            if len(row) < 6:  # Need at least 6 elements including account_id
                skip_reason = "incomplete data (merged cell or missing columns)"
                title = row[0] if len(row) > 0 else "No title"
                print(f"\n{Fore.YELLOW}Skipping incomplete row {i}/{len(rows)}: {title} ({skip_reason}){Style.RESET_ALL}")
                skipped_tickets.append({
                    'title': title,
                    'reason': skip_reason
                })
                continue
                
            print(f"\n{Fore.YELLOW}{'='*60}{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}Task {i}/{len(rows)}: {row[0]}{Style.RESET_ALL}")
            print(f"Priority: {row[1]}")
            print(f"Effort: {row[2]}")
            print(f"Owner: {row[3]}")
            print(f"Note: {row[4]}")
            print(f"{Fore.YELLOW}{'='*60}{Style.RESET_ALL}")
            
            # Create ticket automatically
            print(f"{Fore.GREEN}Creating ticket for: {row[0]}{Style.RESET_ALL}")
            total_attempted += 1
            ticket = create_jira_ticket(row, dri_account_id, epic_key)
            if ticket:
                print(f"{Fore.GREEN}✓ Successfully created: {ticket['key']}{Style.RESET_ALL}")
                successful_count += 1
            else:
                print(f"{Fore.RED}✗ Failed to create ticket{Style.RESET_ALL}")
                
        except IndexError as e:
            skip_reason = "index error accessing row data (likely merged cell)"
            title = row[0] if len(row) > 0 else "No title"
            print(f"\n{Fore.YELLOW}Skipping malformed row {i}/{len(rows)}: {title} ({skip_reason}){Style.RESET_ALL}")
            print(f"{Fore.YELLOW}Row data: {row}{Style.RESET_ALL}")
            skipped_tickets.append({
                'title': title,
                'reason': skip_reason
            })
            continue
        except Exception as e:
            skip_reason = f"exception: {str(e)}"
            title = row[0] if len(row) > 0 else "No title"
            print(f"\n{Fore.RED}Error processing row {i}/{len(rows)}: {title} ({skip_reason}){Style.RESET_ALL}")
            print(f"{Fore.YELLOW}Row data: {row}{Style.RESET_ALL}")
            skipped_tickets.append({
                'title': title,
                'reason': skip_reason
            })
            continue
    
    # Print summary
    print(f"\n{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
    if total_attempted == 0:
        print(f"{Fore.YELLOW}No tickets were attempted (all rows were skipped){Style.RESET_ALL}")
    else:
        success_rate = (successful_count / total_attempted) * 100
        if successful_count == total_attempted:
            print(f"{Fore.GREEN}✓ {successful_count}/{total_attempted} tickets successfully created (100%){Style.RESET_ALL}")
        else:
            print(f"{Fore.YELLOW}✓ {successful_count}/{total_attempted} tickets successfully created ({success_rate:.1f}%){Style.RESET_ALL}")
            if successful_count < total_attempted:
                failed_count = total_attempted - successful_count
                print(f"{Fore.RED}✗ {failed_count} tickets failed to create{Style.RESET_ALL}")
    
    # Display skipped tickets
    if skipped_tickets:
        print(f"\n{Fore.YELLOW}SKIPPED TICKETS ({len(skipped_tickets)} total):{Style.RESET_ALL}")
        for skip_info in skipped_tickets:
            print(f"{Fore.YELLOW}  ✗ {skip_info['title']} - {skip_info['reason']}{Style.RESET_ALL}")
    
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
    
    return successful_count, total_attempted, skipped_tickets

def main():
    """
    Main function to create tickets from Confluence pages using epic.json
    Usage:
      python create_ticket.py                     # Interactive mode - select from epic.json
      python create_ticket.py <page_id>          # Direct mode - use specific page ID
    """
    
    # Show help if requested
    if handle_help_request([
        "python create_ticket.py                     # Interactive mode - select from epic.json",
        "python create_ticket.py <page_id>          # Direct mode - use specific page ID",
        "python create_ticket.py all                # Process all pages with page-level confirmation",
        "",
        "Interactive mode allows you to:",
        "- Select a specific page: creates all tickets automatically",
        "- Select 'ALL PAGES': asks for confirmation on each page, then creates all tickets automatically",
        "",
        "This script creates Jira tickets from Confluence pages using page IDs from epic.json",
        "Tickets will be automatically linked to their parent epics when available."
    ]):
        return
    
    # Validate configuration
    if not handle_config_validation():
        return

    # Check if page ID provided as command line argument
    page_selection = None
    if len(sys.argv) > 1:
        page_selection = sys.argv[1]
        if page_selection.lower() == 'all':
            page_selection = 'all'
            print(f"{Fore.MAGENTA}Processing all pages from command line{Style.RESET_ALL}")
        else:
            print(f"{Fore.CYAN}Using page ID from command line: {page_selection}{Style.RESET_ALL}")
    else:
        page_selection = select_page_interactive()
        if not page_selection:
            return
    
    # Handle "all pages" case
    if page_selection == 'all':
        process_all_pages_with_confirmation()
        print(f"\n{Fore.GREEN}Done!{Style.RESET_ALL}")
        return
    
    # Handle single page case
    page_id = page_selection
    print(f"\n{Fore.GREEN}Fetching table from Confluence page {page_id}...{Style.RESET_ALL}")
    
    # Look up the epic for this page
    epic_key = find_epic_for_page(page_id)
    
    # Use main.py's get_scope_table function to get the data without creating tickets
    result = get_scope_table(page_id, create_tickets=False)
    
    if result and len(result) == 2:
        rows, dri_account_id = result
        successful, attempted, skipped = process_tickets_interactively(rows, dri_account_id, epic_key)
    else:
        print(f"{Fore.RED}Failed to extract table data from the page.{Style.RESET_ALL}")
    
    print(f"\n{Fore.GREEN}Done!{Style.RESET_ALL}")

if __name__ == "__main__":
    main() 