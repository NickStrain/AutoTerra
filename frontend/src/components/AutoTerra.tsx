import React, { useState } from 'react';
import { 
  Send, 
  CheckCircle, 
  AlertTriangle, 
  Download, 
  Loader2, 
  FileText, 
  Code, 
  Shield, 
  DollarSign,
  Terminal,
  Sparkles,
  Github,
  FolderGit2,
  X,
  Search,
  ExternalLink,
  Lock,
  Unlock,
  FileCode
} from 'lucide-react';

interface Requirements {
  required_variables?: string[];
  optional_configs?: string[];
  user_provided_values?: Record<string, string>;
}

interface ValidationData {
  is_valid: boolean;
  score: number;
  issues_count: number;
}

interface Result {
  terraform_code: string;
  requirements: Requirements;
  variables: Record<string, string>;
  used_variables?: string[];
  unused_variables?: string[];
  validation_summary?: Record<string, ValidationData>;
}

interface Repository {
  id: number;
  name: string;
  full_name: string;
  private: boolean;
  description: string;
  updated_at: string;
  html_url: string;
  has_terraform?: boolean;
}

interface TerraformFile {
  path: string;
  content: string;
  file_type: string;
  resources: string[];
  providers: string[];
}

const AutoTerra = () => {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [stage, setStage] = useState('');
  const [variables, setVariables] = useState<Record<string, string>>({});
  const [requiresInput, setRequiresInput] = useState(false);
  const [requirements, setRequirements] = useState<Requirements | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState('');

  // GitHub Integration State
  const [showGithubModal, setShowGithubModal] = useState(false);
  const [githubToken, setGithubToken] = useState('');
  const [githubStep, setGithubStep] = useState<'auth' | 'repos' | 'extracting'>('auth');
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [selectedRepos, setSelectedRepos] = useState<Set<number>>(new Set());
  const [searchTerm, setSearchTerm] = useState('');
  const [filterTerraform, setFilterTerraform] = useState(false);
  const [extractedFiles, setExtractedFiles] = useState<TerraformFile[]>([]);

  const API_URL = 'http://localhost:8000';

  const handleSubmit = async () => {
    if (!query.trim()) return;

    setLoading(true);
    setError('');
    setStage('Analyzing query...');
    setResult(null);

    try {
      const response = await fetch(`${API_URL}/api/analyze-query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query })
      });

      if (!response.ok) throw new Error('Failed to analyze query');

      const data = await response.json();
      setRequirements(data.requirements);
      setVariables(data.requirements.user_provided_values || {});

      if (data.requirements.required_variables?.length > 0) {
        setRequiresInput(true);
        setStage('');
        setLoading(false);
      } else {
        await generateCode(data.requirements, data.requirements.user_provided_values || {});
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
      setLoading(false);
    }
  };

  const handleVariableChange = (key: string, value: string) => {
    setVariables(prev => ({ ...prev, [key]: value }));
  };

  const handleGenerate = async () => {
    await generateCode(requirements!, variables);
  };

  const generateCode = async (reqs: Requirements, vars: Record<string, string>) => {
    setLoading(true);
    setRequiresInput(false);
    setStage('Generating Terraform code...');

    try {
      const response = await fetch(`${API_URL}/api/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query,
          requirements: reqs,
          variables: vars
        })
      });

      if (!response.ok) throw new Error('Failed to generate code');

      const data = await response.json();
      setResult(data);
      setStage('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  const downloadCode = () => {
    if (!result) return;
    const blob = new Blob([result.terraform_code], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `terraform_${Date.now()}.tf`;
    a.click();
  };

  const downloadMetadata = () => {
    if (!result) return;
    const metadata = {
      query,
      requirements: result.requirements,
      variables: result.variables,
      validation: result.validation_summary,
      timestamp: new Date().toISOString()
    };
    const blob = new Blob([JSON.stringify(metadata, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `terraform_metadata_${Date.now()}.json`;
    a.click();
  };

  // GitHub Functions
  const fetchRepositories = async () => {
    if (!githubToken.trim()) {
      setError('Please enter a GitHub token');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = await fetch('https://api.github.com/user/repos?per_page=100&sort=updated', {
        headers: {
          'Authorization': `Bearer ${githubToken}`,
          'Accept': 'application/vnd.github.v3+json'
        }
      });

      if (!response.ok) {
        throw new Error('Failed to fetch repositories. Check your token.');
      }

      const repos: Repository[] = await response.json();
      const reposWithTerraformCheck = await Promise.all(
        repos.map(async (repo) => {
          try {
            const contentsResponse = await fetch(
              `https://api.github.com/repos/${repo.full_name}/contents`,
              {
                headers: {
                  'Authorization': `Bearer ${githubToken}`,
                  'Accept': 'application/vnd.github.v3+json'
                }
              }
            );
            if (contentsResponse.ok) {
              const contents = await contentsResponse.json();
              const hasTerraform = contents.some((item: any) => 
                item.name.endsWith('.tf') || item.name.endsWith('.tfvars')
              );
              return { ...repo, has_terraform: hasTerraform };
            }
          } catch {
            // Ignore errors
          }
          return { ...repo, has_terraform: false };
        })
      );

      setRepositories(reposWithTerraformCheck);
      setGithubStep('repos');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch repositories');
    } finally {
      setLoading(false);
    }
  };

  const extractTerraformFiles = async () => {
    if (selectedRepos.size === 0) {
      setError('Please select at least one repository');
      return;
    }

    setLoading(true);
    setError('');
    setGithubStep('extracting');

    try {
      // Get selected repository details
      const selectedReposList = Array.from(selectedRepos).map(repoId => {
        const repo = repositories.find(r => r.id === repoId);
        return repo ? {
          id: repo.id,
          name: repo.name,
          full_name: repo.full_name,
          html_url: repo.html_url,
          private: repo.private,
          description: repo.description
        } : null;
      }).filter(r => r !== null);

      // Send to backend for extraction
      const response = await fetch(`${API_URL}/api/extract-github`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          github_token: githubToken,
          repositories: selectedReposList
        })
      });

      if (!response.ok) {
        throw new Error('Failed to extract from GitHub');
      }

      const data = await response.json();
      // Update UI with results
      setExtractedFiles(data.files || []);
      setShowGithubModal(false);
      setGithubStep('auth');
      setSelectedRepos(new Set());

      // Populate query with extraction summary
      if (data.total_files > 0) {
        const summary = `Extracted ${data.total_files} Terraform files from ${data.repositories_processed} GitHub repository(ies)`;
        setQuery(summary);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to extract from GitHub');
      setGithubStep('repos');
    } finally {
      setLoading(false);
    }
  };

  const toggleRepo = (repoId: number) => {
    const newSelected = new Set(selectedRepos);
    if (newSelected.has(repoId)) {
      newSelected.delete(repoId);
    } else {
      newSelected.add(repoId);
    }
    setSelectedRepos(newSelected);
  };

  const getFilteredRepos = () => {
    let filtered = repositories;
    if (filterTerraform) {
      filtered = filtered.filter(r => r.has_terraform);
    }
    if (searchTerm) {
      filtered = filtered.filter(r => 
        r.full_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        r.description?.toLowerCase().includes(searchTerm.toLowerCase())
      );
    }
    return filtered;
  };

  const filteredRepos = getFilteredRepos();

  const examples = [
    "Create S3 bucket named data-prod in us-west-2 with ACL private",
    "Deploy EC2 instance named web-server type t2.micro in us-east-1",
    "Create RDS MySQL database db.t3.small with versioning"
  ];

  return (
    <div className="min-h-screen bg-background">
      <div className="fixed inset-0 bg-[linear-gradient(to_right,hsl(var(--border)/0.3)_1px,transparent_1px),linear-gradient(to_bottom,hsl(var(--border)/0.3)_1px,transparent_1px)] bg-[size:64px_64px] pointer-events-none" />
      <div className="relative max-w-5xl mx-auto px-6 py-12">
        <header className="text-center mb-12 animate-fade-in">
          <div className="inline-flex items-center gap-2 px-3 py-1 bg-primary/10 border border-primary/20 rounded-full text-primary text-sm mb-6">
            <Sparkles className="w-4 h-4" />
            <span>AI-Powered Infrastructure</span>
          </div>
          <h1 className="text-5xl font-semibold tracking-tight mb-3">
            <span className="text-gradient">auto</span>
            <span className="text-foreground">terra</span>
          </h1>
          <p className="text-muted-foreground text-lg">
            Generate production-ready Terraform code with natural language
          </p>
        </header>

        <section className="card-minimal mb-8 animate-slide-up" style={{ animationDelay: '0.1s' }}>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-muted-foreground text-sm">
                <Terminal className="w-4 h-4" />
                <span>Describe your infrastructure</span>
              </div>
              <button
                onClick={() => setShowGithubModal(true)}
                className="btn-ghost flex items-center gap-2"
              >
                <Github className="w-4 h-4" />
                <span>Import from GitHub</span>
              </button>
            </div>

            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Example: Create an S3 bucket named data-prod in us-west-2 with ACL public-read and versioning enabled"
              className="input-minimal h-32 resize-none font-mono text-sm"
              disabled={loading}
            />

            <div className="flex flex-col sm:flex-row gap-3 sm:items-center sm:justify-between">
              <button
                onClick={handleSubmit}
                disabled={loading || !query.trim()}
                className="btn-primary"
              >
                {loading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Send className="w-4 h-4" />
                )}
                {loading ? 'Processing...' : 'Generate'}
              </button>

              <div className="flex flex-wrap gap-2">
                {examples.map((example, i) => (
                  <button
                    key={i}
                    onClick={() => setQuery(example)}
                    className="btn-ghost"
                  >
                    {example.split(' ').slice(0, 3).join(' ')}...
                  </button>
                ))}
              </div>
            </div>

            {extractedFiles.length > 0 && (
              <div className="mt-4 p-4 bg-primary/5 border border-primary/20 rounded-lg">
                <div className="flex items-center gap-2 text-primary text-sm mb-2">
                  <CheckCircle className="w-4 h-4" />
                  <span className="font-medium">
                    {extractedFiles.length} Terraform files imported from GitHub
                  </span>
                </div>
                <div className="text-muted-foreground text-xs">
                  Files are ready for analysis and generation
                </div>
              </div>
            )}
          </div>
        </section>

        {loading && stage && (
          <div className="card-minimal mb-8 animate-fade-in">
            <div className="flex items-center gap-3">
              <div className="relative">
                <Loader2 className="w-5 h-5 text-primary animate-spin" />
                <div className="absolute inset-0 animate-pulse-glow rounded-full" />
              </div>
              <span className="text-foreground font-medium">{stage}</span>
            </div>
          </div>
        )}

        {error && (
          <div className="card-minimal border-destructive/30 bg-destructive/5 mb-8 animate-fade-in">
            <div className="flex items-center gap-3">
              <AlertTriangle className="w-5 h-5 text-destructive" />
              <span className="text-destructive">{error}</span>
            </div>
          </div>
        )}

        {requiresInput && requirements && (
          <section className="card-minimal mb-8 animate-slide-up">
            <h2 className="text-xl font-semibold text-foreground mb-6">Required Information</h2>
            {Object.keys(variables).length > 0 && (
              <div className="mb-6">
                <h3 className="text-sm font-medium text-muted-foreground mb-3 uppercase tracking-wider">
                  Extracted from query
                </h3>
                <div className="space-y-2">
                  {Object.entries(variables).map(([key, value]) => (
                    <div key={key} className="badge-success">
                      <CheckCircle className="w-4 h-4" />
                      <span className="font-mono text-sm">{key}: {value}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {requirements.required_variables && requirements.required_variables.length > 0 && (
              <div className="space-y-4 mb-6">
                <h3 className="text-sm font-medium text-muted-foreground uppercase tracking-wider">
                  Required fields
                </h3>
                {requirements.required_variables.map((varName) => (
                  <div key={varName}>
                    <label className="block text-foreground text-sm font-medium mb-2">
                      {varName}
                    </label>
                    <input
                      type="text"
                      value={variables[varName] || ''}
                      onChange={(e) => handleVariableChange(varName, e.target.value)}
                      className="input-minimal font-mono"
                      placeholder={`Enter ${varName}`}
                    />
                  </div>
                ))}
              </div>
            )}

            {requirements.optional_configs && requirements.optional_configs.length > 0 && (
              <div className="space-y-4 mb-6">
                <h3 className="text-sm font-medium text-muted-foreground uppercase tracking-wider">
                  Optional configurations
                </h3>
                {requirements.optional_configs.map((varName) => (
                  <div key={varName}>
                    <label className="block text-foreground text-sm font-medium mb-2">
                      {varName}
                      <span className="text-muted-foreground ml-2">(optional)</span>
                    </label>
                    <input
                      type="text"
                      value={variables[varName] || ''}
                      onChange={(e) => handleVariableChange(varName, e.target.value)}
                      className="input-minimal font-mono"
                      placeholder={`Enter ${varName}`}
                    />
                  </div>
                ))}
              </div>
            )}

            <button onClick={handleGenerate} className="btn-primary w-full">
              Generate Terraform Code
            </button>
          </section>
        )}

        {result && (
          <div className="space-y-6 animate-slide-up">
            {result.validation_summary && (
              <section className="card-minimal">
                <h2 className="text-lg font-semibold text-foreground mb-4">Validation</h2>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  {Object.entries(result.validation_summary).map(([agent, data]) => {
                    const icons: Record<string, React.ComponentType<{ className?: string }>> = {
                      validator: Code,
                      security: Shield,
                      cost_optimizer: DollarSign
                    };
                    const Icon = icons[agent] || CheckCircle;
                    return (
                      <div 
                        key={agent} 
                        className="bg-secondary/50 rounded-lg p-4 border border-border/50"
                      >
                        <div className="flex items-center gap-2 mb-3">
                          <Icon className="w-4 h-4 text-primary" />
                          <span className="text-foreground font-medium text-sm capitalize">
                            {agent.replace('_', ' ')}
                          </span>
                        </div>
                        <div className="space-y-2">
                          <div className="flex items-center justify-between">
                            <span className="text-muted-foreground text-xs">Status</span>
                            {data.is_valid ? (
                              <span className="text-success text-xs font-medium">Valid</span>
                            ) : (
                              <span className="text-warning text-xs font-medium">Issues</span>
                            )}
                          </div>
                          <div className="flex items-center justify-between">
                            <span className="text-muted-foreground text-xs">Score</span>
                            <span className="text-foreground text-xs font-mono">
                              {(data.score * 100).toFixed(0)}%
                            </span>
                          </div>
                          {data.issues_count > 0 && (
                            <div className="text-warning text-xs">
                              {data.issues_count} issue(s)
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </section>
            )}

            {result.variables && Object.keys(result.variables).length > 0 && (
              <section className="card-minimal">
                <h2 className="text-lg font-semibold text-foreground mb-4">Variables</h2>
                <div className="space-y-2">
                  {result.used_variables?.map((varName) => (
                    <div key={varName} className="badge-success">
                      <CheckCircle className="w-4 h-4" />
                      <span className="font-mono text-sm">
                        {varName}: {result.variables[varName]}
                      </span>
                    </div>
                  ))}
                  {result.unused_variables?.map((varName) => (
                    <div key={varName} className="badge-warning">
                      <AlertTriangle className="w-4 h-4" />
                      <span className="font-mono text-sm">
                        {varName}: {result.variables[varName]} (unused)
                      </span>
                    </div>
                  ))}
                </div>
              </section>
            )}

            <section className="card-minimal">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-4">
                <h2 className="text-lg font-semibold text-foreground">Generated Code</h2>
                <div className="flex gap-2">
                  <button onClick={downloadCode} className="btn-secondary">
                    <Download className="w-4 h-4" />
                    <span>.tf</span>
                  </button>
                  <button onClick={downloadMetadata} className="btn-secondary">
                    <FileText className="w-4 h-4" />
                    <span>JSON</span>
                  </button>
                </div>
              </div>
              <div className="relative">
                <pre className="bg-background p-4 rounded-lg overflow-x-auto border border-border font-mono text-sm">
                  <code className="text-primary">
                    {result.terraform_code}
                  </code>
                </pre>
              </div>
            </section>
          </div>
        )}

        <footer className="mt-16 text-center">
          <p className="text-muted-foreground text-sm">
            Built with RAG & Multi-Agent Validation
          </p>
        </footer>
      </div>

      {/* GitHub Modal */}
      {showGithubModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-background border border-border rounded-2xl max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col">
            <div className="flex items-center justify-between p-6 border-b border-border">
              <div className="flex items-center gap-3">
                <Github className="w-6 h-6 text-primary" />
                <h2 className="text-xl font-semibold">Import from GitHub</h2>
              </div>
              <button
                onClick={() => {
                  setShowGithubModal(false);
                  setGithubStep('auth');
                  setError('');
                }}
                className="p-2 hover:bg-secondary rounded-lg transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-6">
              {githubStep === 'auth' && (
                <div className="space-y-4 max-w-xl mx-auto">
                  <div>
                    <label className="block text-sm font-medium text-foreground mb-2">
                      GitHub Personal Access Token
                    </label>
                    <input
                      type="password"
                      value={githubToken}
                      onChange={(e) => setGithubToken(e.target.value)}
                      placeholder="ghp_xxxxxxxxxxxxxxxxxxxx"
                      className="input-minimal font-mono"
                    />
                  </div>

                  <div className="bg-primary/5 border border-primary/20 rounded-lg p-4">
                    <p className="text-primary text-sm mb-2 font-medium">How to get a token:</p>
                    <ol className="text-muted-foreground text-sm space-y-1 list-decimal list-inside">
                      <li>Go to GitHub Settings → Developer settings</li>
                      <li>Generate new token (classic)</li>
                      <li>Select <code className="bg-secondary px-1 rounded">repo</code> scope</li>
                      <li>Copy and paste the token here</li>
                    </ol>
                  </div>

                  <button
                    onClick={fetchRepositories}
                    disabled={loading || !githubToken.trim()}
                    className="btn-primary w-full"
                  >
                    {loading ? (
                      <Loader2 className="w-5 h-5 animate-spin" />
                    ) : (
                      <Github className="w-5 h-5" />
                    )}
                    {loading ? 'Fetching...' : 'Connect & Fetch Repositories'}
                  </button>
                </div>
              )}

              {githubStep === 'repos' && (
                <div className="space-y-4">
                  <div className="flex flex-col md:flex-row gap-3">
                    <div className="flex-1 relative">
                      <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                      <input
                        type="text"
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        placeholder="Search repositories..."
                        className="input-minimal pl-10"
                      />
                    </div>
                    <button
                      onClick={() => setFilterTerraform(!filterTerraform)}
                      className={`btn-ghost ${filterTerraform ? 'bg-primary/10 text-primary' : ''}`}
                    >
                      <FileCode className="w-4 h-4" />
                      Terraform Only
                    </button>
                  </div>

                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">
                      {filteredRepos.length} repositories • {selectedRepos.size} selected
                    </span>
                    {selectedRepos.size > 0 && (
                      <button
                        onClick={extractTerraformFiles}
                        className="btn-primary"
                      >
                        Extract from {selectedRepos.size} repo{selectedRepos.size !== 1 ? 's' : ''}
                      </button>
                    )}
                  </div>

                  <div className="space-y-2 max-h-96 overflow-y-auto">
                    {filteredRepos.map((repo) => (
                      <div
                        key={repo.id}
                        onClick={() => toggleRepo(repo.id)}
                        className={`p-4 rounded-lg border cursor-pointer transition-all ${
                          selectedRepos.has(repo.id)
                            ? 'border-primary bg-primary/5'
                            : 'border-border hover:border-muted-foreground'
                        }`}
                      >
                        <div className="flex items-start gap-3">
                          <div className={`mt-1 w-5 h-5 rounded border-2 flex items-center justify-center ${
                            selectedRepos.has(repo.id)
                              ? 'bg-primary border-primary'
                              : 'border-muted-foreground'
                          }`}>
                            {selectedRepos.has(repo.id) && (
                              <CheckCircle className="w-4 h-4 text-background" />
                            )}
                          </div>

                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                              <FolderGit2 className="w-4 h-4 text-primary flex-shrink-0" />
                              <span className="font-medium truncate">{repo.full_name}</span>
                              {repo.private ? (
                                <Lock className="w-3 h-3 text-muted-foreground" />
                              ) : (
                                <Unlock className="w-3 h-3 text-muted-foreground" />
                              )}
                              {repo.has_terraform && (
                                <span className="px-2 py-0.5 bg-success/10 text-success text-xs rounded-full">
                                  Terraform
                                </span>
                              )}
                            </div>
                            {repo.description && (
                              <p className="text-muted-foreground text-sm mb-2">{repo.description}</p>
                            )}
                            <div className="flex items-center gap-3 text-xs text-muted-foreground">
                              <span>Updated {new Date(repo.updated_at).toLocaleDateString()}</span>
                              <a
                                href={repo.html_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                onClick={(e) => e.stopPropagation()}
                                className="flex items-center gap-1 text-primary hover:underline"
                              >
                                <ExternalLink className="w-3 h-3" />
                                View
                              </a>
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}

                    {filteredRepos.length === 0 && (
                      <div className="text-center py-12">
                        <FileCode className="w-12 h-12 text-muted-foreground mx-auto mb-4 opacity-20" />
                        <p className="text-muted-foreground">No repositories found</p>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {githubStep === 'extracting' && (
                <div className="text-center py-12">
                  <Loader2 className="w-12 h-12 text-primary animate-spin mx-auto mb-4" />
                  <h3 className="text-lg font-semibold mb-2">Extracting Terraform Files</h3>
                  <p className="text-muted-foreground">Processing selected repositories...</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AutoTerra;
