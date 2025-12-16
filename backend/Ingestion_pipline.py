"""
Terraform Code Extraction System
Extracts Terraform code from GitHub repositories and returns the content
User can select repositories interactively
"""

import os
import re
import json
import hashlib
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from github import Github, Repository
from dotenv import load_dotenv

load_dotenv()


@dataclass
class TerraformFile:
    """Represents a Terraform file"""
    path: str
    content: str
    repo_name: str
    repo_url: str
    file_hash: str
    file_type: str  # 'main', 'variables', 'outputs', 'modules', etc.
    resources: List[str]  # List of resource types found
    modules: List[str]  # List of module sources
    providers: List[str]  # List of providers used
    variables: List[str]  # List of variable names
    outputs: List[str]  # List of output names
    size_bytes: int
    last_modified: str
    
    def to_dict(self):
        """Convert to dictionary"""
        return asdict(self)


class TerraformExtractor:
    """Extracts and parses Terraform files from repositories"""
    
    TERRAFORM_EXTENSIONS = {'.tf', '.tfvars', '.hcl'}
    
    def __init__(self):
        self.resource_pattern = re.compile(r'resource\s+"([^"]+)"\s+"([^"]+)"')
        self.module_pattern = re.compile(r'module\s+"([^"]+)"\s*\{[^}]*source\s*=\s*"([^"]+)"', re.DOTALL)
        self.provider_pattern = re.compile(r'provider\s+"([^"]+)"')
        self.variable_pattern = re.compile(r'variable\s+"([^"]+)"')
        self.output_pattern = re.compile(r'output\s+"([^"]+)"')
    
    def is_terraform_file(self, filepath: str) -> bool:
        """Check if file is a Terraform file"""
        return Path(filepath).suffix in self.TERRAFORM_EXTENSIONS
    
    def classify_file_type(self, filepath: str, content: str) -> str:
        """Classify the type of Terraform file"""
        filename = Path(filepath).name.lower()
        
        if 'variables' in filename or filename.startswith('vars'):
            return 'variables'
        elif 'outputs' in filename:
            return 'outputs'
        elif 'providers' in filename or 'terraform' in filename:
            return 'providers'
        elif 'modules' in filename or '/modules/' in filepath:
            return 'module'
        elif 'main' in filename:
            return 'main'
        elif content.strip().startswith('terraform {'):
            return 'terraform_config'
        else:
            return 'resource'
    
    def extract_resources(self, content: str) -> List[str]:
        """Extract resource types from Terraform code"""
        matches = self.resource_pattern.findall(content)
        return [f"{provider}.{name}" for provider, name in matches]
    
    def extract_modules(self, content: str) -> List[str]:
        """Extract module sources from Terraform code"""
        matches = self.module_pattern.findall(content)
        return [source for _, source in matches]
    
    def extract_providers(self, content: str) -> List[str]:
        """Extract providers from Terraform code"""
        return list(set(self.provider_pattern.findall(content)))
    
    def extract_variables(self, content: str) -> List[str]:
        """Extract variable names"""
        return self.variable_pattern.findall(content)
    
    def extract_outputs(self, content: str) -> List[str]:
        """Extract output names"""
        return self.output_pattern.findall(content)
    
    def parse_terraform_file(self, filepath: str, content: str, 
                            repo_name: str, repo_url: str, 
                            last_modified: str) -> TerraformFile:
        """Parse a Terraform file and extract metadata"""
        file_hash = hashlib.sha256(content.encode()).hexdigest()
        file_type = self.classify_file_type(filepath, content)
        
        return TerraformFile(
            path=filepath,
            content=content,
            repo_name=repo_name,
            repo_url=repo_url,
            file_hash=file_hash,
            file_type=file_type,
            resources=self.extract_resources(content),
            modules=self.extract_modules(content),
            providers=self.extract_providers(content),
            variables=self.extract_variables(content),
            outputs=self.extract_outputs(content),
            size_bytes=len(content.encode()),
            last_modified=last_modified
        )


class GitHubConnector:
    """Connects to GitHub and fetches Terraform repositories"""
    
    def __init__(self, github_token: str):
        self.github = Github(github_token)
        self.extractor = TerraformExtractor()
        self.user = self.github.get_user()
    
    def list_user_repositories(self, include_private: bool = True) -> List[Repository]:
        """List all repositories for the authenticated user"""
        try:
            repos = []
            for repo in self.user.get_repos():
                if include_private or not repo.private:
                    repos.append(repo)
            return repos
        except Exception as e:
            print(f"ERROR: Error listing repositories: {e}")
            return []
    
    def filter_terraform_repositories(self, repos: List[Repository]) -> List[Repository]:
        """Filter repositories that likely contain Terraform code"""
        terraform_repos = []
        
        print("\nScanning repositories for Terraform code...")
        for repo in repos:
            try:
                # Quick check: look for .tf files in root
                contents = repo.get_contents("")
                has_terraform = any(
                    self.extractor.is_terraform_file(item.name) 
                    for item in contents 
                    if item.type == "file"
                )
                
                if has_terraform:
                    terraform_repos.append(repo)
                    print(f"  Found Terraform in: {repo.full_name}")
            except:
                pass
        
        return terraform_repos
    
    def display_repositories_menu(self, repos: List[Repository]) -> List[Repository]:
        """Display repositories and let user select which ones to extract"""
        print("\n" + "="*70)
        print("YOUR REPOSITORIES")
        print("="*70)
        
        for idx, repo in enumerate(repos, 1):
            visibility = "Private" if repo.private else "Public"
            updated = repo.updated_at.strftime("%Y-%m-%d")
            print(f"{idx:3d}. [{visibility:7s}] {repo.full_name:50s} (Updated: {updated})")
        
        print("\n" + "="*70)
        print("Select repositories to extract (comma-separated numbers)")
        print("Examples: 1,3,5  or  1-5  or  'all'  or  'q' to quit")
        print("="*70)
        
        while True:
            selection = input("\nYour selection: ").strip().lower()
            
            if selection == 'q':
                return []
            
            if selection == 'all':
                return repos
            
            try:
                selected_repos = []
                
                # Handle ranges (e.g., 1-5)
                if '-' in selection:
                    parts = selection.split('-')
                    start = int(parts[0])
                    end = int(parts[1])
                    for i in range(start, end + 1):
                        if 1 <= i <= len(repos):
                            selected_repos.append(repos[i-1])
                
                # Handle comma-separated (e.g., 1,3,5)
                elif ',' in selection:
                    indices = [int(x.strip()) for x in selection.split(',')]
                    for i in indices:
                        if 1 <= i <= len(repos):
                            selected_repos.append(repos[i-1])
                
                # Handle single number
                else:
                    i = int(selection)
                    if 1 <= i <= len(repos):
                        selected_repos.append(repos[i-1])
                
                if selected_repos:
                    print(f"\nSelected {len(selected_repos)} repository(ies):")
                    for repo in selected_repos:
                        print(f"  - {repo.full_name}")
                    
                    confirm = input("\nProceed with extraction? (y/n): ").strip().lower()
                    if confirm == 'y':
                        return selected_repos
                else:
                    print("No valid repositories selected. Try again.")
            
            except ValueError:
                print("Invalid input. Please use format: 1,3,5 or 1-5 or 'all'")
    
    def fetch_repo(self, repo_name: str) -> Repository:
        """Fetch a GitHub repository"""
        try:
            return self.github.get_repo(repo_name)
        except Exception as e:
            print(f"ERROR: Error fetching repo {repo_name}: {e}")
            raise
    
    def extract_terraform_files_from_repo(self, repo: Repository, 
                                         skip_dirs: List[str] = None) -> List[TerraformFile]:
        """Extract all Terraform files from a repository"""
        if skip_dirs is None:
            skip_dirs = ['.git', 'test', 'example', 'examples', '.terraform', 'tests']
        
        terraform_files = []
        
        try:
            print(f"\nProcessing repository: {repo.full_name}")
            contents = repo.get_contents("")
            
            while contents:
                file_content = contents.pop(0)
                
                if file_content.type == "dir":
                    # Skip certain directories
                    if any(skip in file_content.path for skip in skip_dirs):
                        continue
                    contents.extend(repo.get_contents(file_content.path))
                
                elif self.extractor.is_terraform_file(file_content.path):
                    try:
                        content = file_content.decoded_content.decode('utf-8')
                        tf_file = self.extractor.parse_terraform_file(
                            filepath=file_content.path,
                            content=content,
                            repo_name=repo.full_name,
                            repo_url=repo.html_url,
                            last_modified=file_content.last_modified
                        )
                        terraform_files.append(tf_file)
                        print(f"  Extracted: {file_content.path} ({tf_file.file_type})")
                    except Exception as e:
                        print(f"  ERROR processing {file_content.path}: {e}")
            
            print(f"  Total Terraform files found: {len(terraform_files)}")
            
        except Exception as e:
            print(f"ERROR: Error processing repository {repo.full_name}: {e}")
        
        return terraform_files


class TerraformExtractionPipeline:
    """Main extraction pipeline"""
    
    def __init__(self, github_token: str):
        self.github_connector = GitHubConnector(github_token)
    
    def interactive_extraction(self) -> List[Dict]:
        """Interactive mode: let user select repositories"""
        print("\n" + "="*70)
        print("TERRAFORM EXTRACTION - INTERACTIVE MODE")
        print("="*70)
        
        # Get authenticated user info
        user = self.github_connector.user
        print(f"\nAuthenticated as: {user.login}")
        print(f"Name: {user.name}")
        
        # List all repositories
        print("\nFetching your repositories...")
        all_repos = self.github_connector.list_user_repositories(include_private=True)
        print(f"Found {len(all_repos)} total repositories")
        
        # Filter for Terraform repositories
        print("\nWould you like to:")
        print("1. See all repositories")
        print("2. See only repositories with Terraform code (faster)")
        choice = input("\nYour choice (1 or 2): ").strip()
        
        if choice == '2':
            repos_to_show = self.github_connector.filter_terraform_repositories(all_repos)
            if not repos_to_show:
                print("\nNo Terraform repositories found. Showing all repositories instead.")
                repos_to_show = all_repos
        else:
            repos_to_show = all_repos
        
        # Let user select repositories
        selected_repos = self.github_connector.display_repositories_menu(repos_to_show)
        
        if not selected_repos:
            print("\nNo repositories selected. Exiting.")
            return []
        
        # Extract from selected repositories
        results = []
        for repo in selected_repos:
            try:
                result = self.extract_from_repository(repo)
                results.append(result)
            except Exception as e:
                print(f"ERROR: Error extracting from {repo.full_name}: {e}")
                results.append({
                    'status': 'error',
                    'repo_name': repo.full_name,
                    'error': str(e),
                    'files': [],
                    'count': 0
                })
        
        return results
    
    def extract_from_repository(self, repo: Repository) -> Dict:
        """Extract Terraform files from a single repository"""
        print(f"\n{'='*70}")
        print(f"EXTRACTING FROM REPOSITORY: {repo.full_name}")
        print(f"{'='*70}")
        
        # Extract Terraform files
        tf_files = self.github_connector.extract_terraform_files_from_repo(repo)
        
        if not tf_files:
            print(f"WARNING: No Terraform files found in {repo.full_name}")
            return {
                'status': 'no_files', 
                'repo_name': repo.full_name,
                'files': [],
                'count': 0
            }
        
        print(f"\n{'='*70}")
        print(f"EXTRACTION COMPLETE")
        print(f"{'='*70}")
        
        return {
            'status': 'success',
            'repo_name': repo.full_name,
            'files': [tf_file.to_dict() for tf_file in tf_files],
            'count': len(tf_files),
            'timestamp': datetime.now().isoformat()
        }
    
    def save_to_json(self, results: List[Dict], output_file: str = "terraform_extracted.json"):
        """Save extraction results to JSON file"""
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to: {output_file}")
    
    def save_to_separate_files(self, results: List[Dict], output_dir: str = "extracted_terraform"):
        """Save each Terraform file separately"""
        os.makedirs(output_dir, exist_ok=True)
        
        for result in results:
            if result['status'] == 'success':
                repo_name = result['repo_name'].replace('/', '_')
                repo_dir = os.path.join(output_dir, repo_name)
                os.makedirs(repo_dir, exist_ok=True)
                
                for tf_file in result['files']:
                    # Create subdirectories as needed
                    file_path = tf_file['path']
                    full_path = os.path.join(repo_dir, file_path)
                    os.makedirs(os.path.dirname(full_path), exist_ok=True)
                    
                    # Save the file
                    with open(full_path, 'w') as f:
                        f.write(tf_file['content'])
                    
                    # Save metadata
                    metadata = {k: v for k, v in tf_file.items() if k != 'content'}
                    metadata_path = full_path + '.metadata.json'
                    with open(metadata_path, 'w') as f:
                        json.dump(metadata, f, indent=2)
        
        print(f"\nFiles saved to directory: {output_dir}")


def main():
    """Main execution function"""
    print("TERRAFORM CODE EXTRACTION SYSTEM")
    print("="*70)
    
    # Load environment variables
    GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
    
    if not GITHUB_TOKEN:
        print("ERROR: GITHUB_TOKEN not found in environment")
        print("\nPlease set your GitHub token:")
        print("1. Create a token at: https://github.com/settings/tokens")
        print("2. Add to .env file: GITHUB_TOKEN=your_token_here")
        return
    
    # Initialize pipeline
    pipeline = TerraformExtractionPipeline(github_token=GITHUB_TOKEN)
    
    # Run interactive extraction
    results = pipeline.interactive_extraction()
    
    if not results:
        return
    
    # Print summary
    print("\n" + "="*70)
    print("EXTRACTION SUMMARY")
    print("="*70)
    
    total_files = 0
    for result in results:
        if result['status'] == 'success':
            print(f"\nSUCCESS: {result['repo_name']}")
            print(f"   Files: {result['count']}")
            total_files += result['count']
            
            # Print breakdown by file type
            file_types = {}
            for tf_file in result['files']:
                file_type = tf_file['file_type']
                file_types[file_type] = file_types.get(file_type, 0) + 1
            
            print(f"   File types: {dict(file_types)}")
        else:
            print(f"\nERROR: {result['repo_name']}")
            print(f"   Error: {result.get('error', 'Unknown error')}")
    
    print(f"\nTotal files extracted: {total_files}")
    
    # Save results
    save_choice = input("\nSave results? (y/n): ").strip().lower()
    if save_choice == 'y':
        pipeline.save_to_json(results, "terraform_extracted.json")
        pipeline.save_to_separate_files(results, "extracted_terraform")
    
    print("\nExtraction pipeline complete!")


if __name__ == "__main__":
    main()