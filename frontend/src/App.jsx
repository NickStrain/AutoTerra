import React, { useState } from 'react';
import { Send, CheckCircle, AlertTriangle, Download, Loader2, FileText, Code, Shield, DollarSign } from 'lucide-react';

const TerraformGenerator = () => {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [stage, setStage] = useState('');
  const [variables, setVariables] = useState({});
  const [requiresInput, setRequiresInput] = useState(false);
  const [requirements, setRequirements] = useState(null);
  const [result, setResult] = useState(null);
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
      setError(err.message);
      setLoading(false);
    }
  };

  const handleVariableChange = (key, value) => {
    setVariables(prev => ({ ...prev, [key]: value }));
  };

  const handleGenerate = async () => {
    await generateCode(requirements, variables);
  };

  const generateCode = async (reqs, vars) => {
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
      setError(err.message);
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

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
      <div className="max-w-7xl mx-auto p-6">
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-white mb-2">
            🏗️ Terraform IaC Generator
          </h1>
          <p className="text-purple-200">AI-Powered Infrastructure as Code with RAG & Validation</p>
        </div>

        <div className="bg-white/10 backdrop-blur-lg rounded-xl p-6 mb-6 border border-white/20">
          <div className="space-y-4">
            <div>
              <label className="block text-white font-medium mb-2">
                Describe your infrastructure:
              </label>
              <textarea
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Example: Create an S3 bucket named data-prod in us-west-2 with ACL public-read and versioning enabled"
                className="w-full h-32 px-4 py-3 bg-white/20 border border-white/30 rounded-lg text-white placeholder-purple-200 focus:outline-none focus:ring-2 focus:ring-purple-500"
                disabled={loading}
              />
            </div>

            <div className="flex gap-3">
              <button
                onClick={handleSubmit}
                disabled={loading || !query.trim()}
                className="flex items-center gap-2 px-6 py-3 bg-purple-600 hover:bg-purple-700 disabled:bg-gray-600 text-white rounded-lg font-medium transition-colors"
              >
                {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
                {loading ? 'Processing...' : 'Generate Code'}
              </button>
            </div>
          </div>

          <div className="mt-4 space-y-2">
            <p className="text-purple-200 text-sm font-medium">Examples:</p>
            <div className="flex flex-wrap gap-2">
              {[
                "Create S3 bucket named data-prod in us-west-2 with ACL private",
                "Deploy EC2 instance named web-server type t2.micro in us-east-1",
                "Create RDS MySQL database db.t3.small with versioning"
              ].map((example, i) => (
                <button
                  key={i}
                  onClick={() => setQuery(example)}
                  className="text-xs px-3 py-1.5 bg-white/10 hover:bg-white/20 border border-white/20 rounded-full text-purple-100 transition-colors"
                >
                  {example}
                </button>
              ))}
            </div>
          </div>
        </div>

        {loading && stage && (
          <div className="bg-white/10 backdrop-blur-lg rounded-xl p-6 mb-6 border border-white/20">
            <div className="flex items-center gap-3">
              <Loader2 className="w-6 h-6 text-purple-400 animate-spin" />
              <span className="text-white font-medium">{stage}</span>
            </div>
          </div>
        )}

        {error && (
          <div className="bg-red-500/20 backdrop-blur-lg rounded-xl p-4 mb-6 border border-red-500/50">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-red-400" />
              <span className="text-red-200">{error}</span>
            </div>
          </div>
        )}

        {requiresInput && requirements && (
          <div className="bg-white/10 backdrop-blur-lg rounded-xl p-6 mb-6 border border-white/20">
            <h2 className="text-2xl font-bold text-white mb-4">Required Information</h2>
            
            {Object.keys(variables).length > 0 && (
              <div className="mb-6">
                <h3 className="text-lg font-semibold text-purple-200 mb-3">Extracted from your query:</h3>
                <div className="space-y-2">
                  {Object.entries(variables).map(([key, value]) => (
                    <div key={key} className="flex items-center gap-2 px-3 py-2 bg-green-500/20 rounded-lg border border-green-500/30">
                      <CheckCircle className="w-4 h-4 text-green-400" />
                      <span className="text-white"><strong>{key}:</strong> {value}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {requirements.required_variables?.length > 0 && (
              <div className="space-y-4 mb-6">
                <h3 className="text-lg font-semibold text-purple-200">Additional required fields:</h3>
                {requirements.required_variables.map((varName) => (
                  <div key={varName}>
                    <label className="block text-white font-medium mb-2">{varName}</label>
                    <input
                      type="text"
                      value={variables[varName] || ''}
                      onChange={(e) => handleVariableChange(varName, e.target.value)}
                      className="w-full px-4 py-2 bg-white/20 border border-white/30 rounded-lg text-white placeholder-purple-200 focus:outline-none focus:ring-2 focus:ring-purple-500"
                      placeholder={`Enter ${varName}`}
                    />
                  </div>
                ))}
              </div>
            )}

            {requirements.optional_configs?.length > 0 && (
              <div className="space-y-4 mb-6">
                <h3 className="text-lg font-semibold text-purple-200">Optional configurations:</h3>
                {requirements.optional_configs.map((varName) => (
                  <div key={varName}>
                    <label className="block text-white font-medium mb-2">{varName} (optional)</label>
                    <input
                      type="text"
                      value={variables[varName] || ''}
                      onChange={(e) => handleVariableChange(varName, e.target.value)}
                      className="w-full px-4 py-2 bg-white/20 border border-white/30 rounded-lg text-white placeholder-purple-200 focus:outline-none focus:ring-2 focus:ring-purple-500"
                      placeholder={`Enter ${varName} (optional)`}
                    />
                  </div>
                ))}
              </div>
            )}

            <button
              onClick={handleGenerate}
              className="w-full px-6 py-3 bg-purple-600 hover:bg-purple-700 text-white rounded-lg font-medium transition-colors"
            >
              Generate Terraform Code
            </button>
          </div>
        )}

        {result && (
          <div className="space-y-6">
            <div className="bg-white/10 backdrop-blur-lg rounded-xl p-6 border border-white/20">
              <h2 className="text-2xl font-bold text-white mb-4">Validation Summary</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                {Object.entries(result.validation_summary || {}).map(([agent, data]) => {
                  const icons = {
                    validator: Code,
                    security: Shield,
                    cost_optimizer: DollarSign
                  };
                  const Icon = icons[agent] || CheckCircle;
                  
                  return (
                    <div key={agent} className="bg-white/5 rounded-lg p-4 border border-white/10">
                      <div className="flex items-center gap-2 mb-2">
                        <Icon className="w-5 h-5 text-purple-400" />
                        <span className="text-white font-medium capitalize">
                          {agent.replace('_', ' ')}
                        </span>
                      </div>
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          {data.is_valid ? (
                            <CheckCircle className="w-4 h-4 text-green-400" />
                          ) : (
                            <AlertTriangle className="w-4 h-4 text-yellow-400" />
                          )}
                          <span className="text-sm text-purple-200">
                            {data.is_valid ? 'Valid' : 'Issues Found'}
                          </span>
                        </div>
                        <div className="text-sm text-purple-200">
                          Score: {(data.score * 100).toFixed(0)}%
                        </div>
                        {data.issues_count > 0 && (
                          <div className="text-sm text-yellow-300">
                            {data.issues_count} issue(s)
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {result.variables && Object.keys(result.variables).length > 0 && (
              <div className="bg-white/10 backdrop-blur-lg rounded-xl p-6 border border-white/20">
                <h2 className="text-2xl font-bold text-white mb-4">Variable Usage</h2>
                <div className="space-y-2">
                  {result.used_variables?.map((varName) => (
                    <div key={varName} className="flex items-center gap-2 px-3 py-2 bg-green-500/20 rounded-lg border border-green-500/30">
                      <CheckCircle className="w-4 h-4 text-green-400" />
                      <span className="text-white">{varName}: {result.variables[varName]}</span>
                    </div>
                  ))}
                  {result.unused_variables?.map((varName) => (
                    <div key={varName} className="flex items-center gap-2 px-3 py-2 bg-red-500/20 rounded-lg border border-red-500/30">
                      <AlertTriangle className="w-4 h-4 text-red-400" />
                      <span className="text-white">{varName}: {result.variables[varName]} (Not used in code)</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="bg-white/10 backdrop-blur-lg rounded-xl p-6 border border-white/20">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-2xl font-bold text-white">Generated Terraform Code</h2>
                <div className="flex gap-2">
                  <button
                    onClick={downloadCode}
                    className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg font-medium transition-colors"
                  >
                    <Download className="w-4 h-4" />
                    Download .tf
                  </button>
                  <button
                    onClick={downloadMetadata}
                    className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors"
                  >
                    <FileText className="w-4 h-4" />
                    Metadata
                  </button>
                </div>
              </div>
              <pre className="bg-slate-900 p-4 rounded-lg overflow-x-auto border border-white/10">
                <code className="text-green-400 text-sm font-mono">
                  {result.terraform_code}
                </code>
              </pre>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default TerraformGenerator;