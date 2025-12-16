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
  Sparkles
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

const AutoTerra = () => {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [stage, setStage] = useState('');
  const [variables, setVariables] = useState<Record<string, string>>({});
  const [requiresInput, setRequiresInput] = useState(false);
  const [requirements, setRequirements] = useState<Requirements | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState('');

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

  const examples = [
    "Create S3 bucket named data-prod in us-west-2 with ACL private",
    "Deploy EC2 instance named web-server type t2.micro in us-east-1",
    "Create RDS MySQL database db.t3.small with versioning"
  ];

  return (
    <div className="min-h-screen bg-background">
      {/* Subtle grid background */}
      <div className="fixed inset-0 bg-[linear-gradient(to_right,hsl(var(--border)/0.3)_1px,transparent_1px),linear-gradient(to_bottom,hsl(var(--border)/0.3)_1px,transparent_1px)] bg-[size:64px_64px] pointer-events-none" />
      
      <div className="relative max-w-5xl mx-auto px-6 py-12">
        {/* Header */}
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

        {/* Input Section */}
        <section className="card-minimal mb-8 animate-slide-up" style={{ animationDelay: '0.1s' }}>
          <div className="space-y-4">
            <div className="flex items-center gap-2 text-muted-foreground text-sm mb-2">
              <Terminal className="w-4 h-4" />
              <span>Describe your infrastructure</span>
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
          </div>
        </section>

        {/* Loading State */}
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

        {/* Error State */}
        {error && (
          <div className="card-minimal border-destructive/30 bg-destructive/5 mb-8 animate-fade-in">
            <div className="flex items-center gap-3">
              <AlertTriangle className="w-5 h-5 text-destructive" />
              <span className="text-destructive">{error}</span>
            </div>
          </div>
        )}

        {/* Required Input Section */}
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

        {/* Results Section */}
        {result && (
          <div className="space-y-6 animate-slide-up">
            {/* Validation Summary */}
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

            {/* Variables Usage */}
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

            {/* Generated Code */}
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

        {/* Footer */}
        <footer className="mt-16 text-center">
          <p className="text-muted-foreground text-sm">
            Built with RAG & Multi-Agent Validation
          </p>
        </footer>
      </div>
    </div>
  );
};

export default AutoTerra;
