"""
============================================================================
ULTRA-ADVANCED RAG WEB APPLICATION
============================================================================
A modern, intelligent document Q&A system with multi-format support
Features: PDF, DOCX, TXT extraction | Real-time chat | Smart embeddings
============================================================================
"""

from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import os
import google.generativeai as genai
import numpy as np
from typing import List, Dict, Tuple
import pickle
from datetime import datetime
from dotenv import load_dotenv
import json
from werkzeug.utils import secure_filename
import traceback

# Document parsers
import PyPDF2
from docx import Document as DocxDocument
import io

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'docx', 'doc'}
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# Create upload folder
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


class AdvancedRAGAgent:
    """Ultra-Advanced RAG Agent with Multi-Format Document Support"""
    
    def __init__(self, api_key: str = None):
        """Initialize the advanced RAG agent"""
        self.api_key = api_key or os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables")
        
        # Configure Gemini
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-2.5-flash')
        self.embedding_model = 'models/text-embedding-004'
        
        # Knowledge base
        self.documents = []  # Text chunks
        self.embeddings = []  # Vector embeddings
        self.metadata = []  # Document metadata (filename, page, etc.)
        self.knowledge_base_file = 'knowledge_base.pkl'
        
        # Statistics
        self.stats = {
            'total_documents': 0,
            'total_chunks': 0,
            'total_queries': 0,
            'last_updated': None
        }
        
        # Load existing knowledge base
        self.load_knowledge_base()
        print("✅ Advanced RAG Agent initialized")
    
    def extract_text_from_pdf(self, file_path: str) -> str:
        """Extract text from PDF file"""
        try:
            text = ""
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page_num, page in enumerate(pdf_reader.pages):
                    page_text = page.extract_text()
                    if page_text:
                        text += f"\n\n--- Page {page_num + 1} ---\n\n{page_text}"
            return text.strip()
        except Exception as e:
            raise Exception(f"PDF extraction error: {str(e)}")
    
    def extract_text_from_docx(self, file_path: str) -> str:
        """Extract text from DOCX file"""
        try:
            doc = DocxDocument(file_path)
            paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
            return "\n\n".join(paragraphs)
        except Exception as e:
            raise Exception(f"DOCX extraction error: {str(e)}")
    
    def extract_text_from_txt(self, file_path: str) -> str:
        """Extract text from TXT file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read()
        except UnicodeDecodeError:
            # Try with different encoding
            with open(file_path, 'r', encoding='latin-1') as file:
                return file.read()
    
    def process_document(self, file_path: str, filename: str) -> Dict:
        """Process any supported document format"""
        file_ext = filename.lower().split('.')[-1]
        
        # Extract text based on file type
        if file_ext == 'pdf':
            text = self.extract_text_from_pdf(file_path)
        elif file_ext in ['docx', 'doc']:
            text = self.extract_text_from_docx(file_path)
        elif file_ext == 'txt':
            text = self.extract_text_from_txt(file_path)
        else:
            raise ValueError(f"Unsupported file format: {file_ext}")
        
        if not text or len(text.strip()) < 10:
            raise ValueError("Document appears to be empty or too short")
        
        # Chunk the text
        chunks = self.chunk_text(text, chunk_size=500, overlap=50)
        
        # Generate embeddings for each chunk
        chunk_count = 0
        for chunk in chunks:
            try:
                embedding = self.get_embedding(chunk)
                self.documents.append(chunk)
                self.embeddings.append(embedding)
                self.metadata.append({
                    'filename': filename,
                    'file_type': file_ext,
                    'added_at': datetime.now().isoformat(),
                    'chunk_index': chunk_count
                })
                chunk_count += 1
            except Exception as e:
                print(f"Warning: Failed to embed chunk {chunk_count}: {e}")
                continue
        
        # Update statistics
        self.stats['total_documents'] += 1
        self.stats['total_chunks'] = len(self.documents)
        self.stats['last_updated'] = datetime.now().isoformat()
        
        # Save knowledge base
        self.save_knowledge_base()
        
        return {
            'filename': filename,
            'file_type': file_ext,
            'text_length': len(text),
            'chunks_created': chunk_count,
            'status': 'success'
        }
    
    def chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """Split text into overlapping chunks"""
        words = text.split()
        chunks = []
        
        for i in range(0, len(words), chunk_size - overlap):
            chunk = ' '.join(words[i:i + chunk_size])
            if chunk.strip():
                chunks.append(chunk)
        
        return chunks
    
    def get_embedding(self, text: str) -> List[float]:
        """Generate embedding vector for text"""
        result = genai.embed_content(
            model=self.embedding_model,
            content=text,
            task_type="retrieval_document"
        )
        return result['embedding']
    
    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        vec1 = np.array(vec1)
        vec2 = np.array(vec2)
        return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))
    
    def retrieve_relevant_chunks(self, query: str, top_k: int = 5) -> List[Tuple[str, float, Dict]]:
        """Retrieve most relevant document chunks for a query"""
        if not self.documents:
            return []
        
        # Get query embedding
        query_embedding = genai.embed_content(
            model=self.embedding_model,
            content=query,
            task_type="retrieval_query"
        )['embedding']
        
        # Calculate similarities
        similarities = []
        for idx, doc_embedding in enumerate(self.embeddings):
            similarity = self.cosine_similarity(query_embedding, doc_embedding)
            similarities.append((self.documents[idx], similarity, self.metadata[idx]))
        
        # Sort by similarity and return top_k
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_k]
    
    def query(self, question: str, top_k: int = 5) -> Dict:
        """Answer a question using RAG"""
        self.stats['total_queries'] += 1
        
        if not self.documents:
            return {
                'answer': "❌ No documents in knowledge base. Please upload documents first.",
                'sources': [],
                'confidence': 0.0
            }
        
        # Retrieve relevant chunks
        relevant_chunks = self.retrieve_relevant_chunks(question, top_k)
        
        if not relevant_chunks:
            return {
                'answer': "❌ No relevant information found in the knowledge base.",
                'sources': [],
                'confidence': 0.0
            }
        
        # Build context from relevant chunks
        context = "\n\n---\n\n".join([chunk[0] for chunk in relevant_chunks])
        
        # Generate answer using Gemini
        prompt = f"""You are an intelligent document analysis assistant. Based on the provided context, answer the user's question accurately and concisely.

Context from documents:
{context}

User Question: {question}

Instructions:
- Provide a clear, accurate answer based on the context
- If the context doesn't contain enough information, say so
- Be specific and reference relevant details
- Keep the answer well-structured and easy to read

Answer:"""
        
        try:
            response = self.model.generate_content(prompt)
            answer = response.text
            
            # Prepare source information
            sources = [{
                'filename': chunk[2]['filename'],
                'relevance': round(chunk[1], 3),
                'snippet': chunk[0][:200] + '...' if len(chunk[0]) > 200 else chunk[0]
            } for chunk in relevant_chunks[:3]]
            
            # Calculate average confidence
            avg_confidence = sum([chunk[1] for chunk in relevant_chunks]) / len(relevant_chunks)
            
            return {
                'answer': answer,
                'sources': sources,
                'confidence': round(avg_confidence, 3),
                'chunks_used': len(relevant_chunks)
            }
        
        except Exception as e:
            return {
                'answer': f"❌ Error generating answer: {str(e)}",
                'sources': [],
                'confidence': 0.0
            }
    
    def save_knowledge_base(self):
        """Save knowledge base to disk"""
        data = {
            'documents': self.documents,
            'embeddings': self.embeddings,
            'metadata': self.metadata,
            'stats': self.stats
        }
        with open(self.knowledge_base_file, 'wb') as f:
            pickle.dump(data, f)
    
    def load_knowledge_base(self):
        """Load knowledge base from disk"""
        if os.path.exists(self.knowledge_base_file):
            try:
                with open(self.knowledge_base_file, 'rb') as f:
                    data = pickle.load(f)
                self.documents = data.get('documents', [])
                self.embeddings = data.get('embeddings', [])
                self.metadata = data.get('metadata', [])
                self.stats = data.get('stats', self.stats)
                print(f"✅ Loaded {len(self.documents)} chunks from knowledge base")
            except Exception as e:
                print(f"⚠ Warning: Could not load knowledge base: {e}")
    
    def clear_knowledge_base(self):
        """Clear all documents from knowledge base"""
        self.documents = []
        self.embeddings = []
        self.metadata = []
        self.stats = {
            'total_documents': 0,
            'total_chunks': 0,
            'total_queries': 0,
            'last_updated': None
        }
        self.save_knowledge_base()
    
    def get_stats(self) -> Dict:
        """Get knowledge base statistics"""
        document_files = list(set([meta['filename'] for meta in self.metadata]))
        return {
            **self.stats,
            'unique_documents': len(document_files),
            'document_list': document_files
        }


# Initialize RAG Agent
try:
    rag_agent = AdvancedRAGAgent()
except Exception as e:
    print(f"❌ Failed to initialize RAG Agent: {e}")
    rag_agent = None


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ============================================================================
# API ROUTES
# ============================================================================

@app.route('/')
def index():
    """Serve the main web interface"""
    return render_template('index.html')


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'agent_initialized': rag_agent is not None,
        'timestamp': datetime.now().isoformat()
    })


@app.route('/api/upload', methods=['POST'])
def upload_document():
    """Upload and process a document"""
    if not rag_agent:
        return jsonify({'error': 'RAG Agent not initialized'}), 500
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': f'Invalid file type. Allowed: {", ".join(ALLOWED_EXTENSIONS)}'}), 400
    
    try:
        # Save file
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        # Process document
        result = rag_agent.process_document(file_path, filename)
        
        # Clean up file
        os.remove(file_path)
        
        return jsonify({
            'success': True,
            'message': f'Document processed successfully',
            'data': result
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


@app.route('/api/query', methods=['POST'])
def query_document():
    """Query the knowledge base"""
    if not rag_agent:
        return jsonify({'error': 'RAG Agent not initialized'}), 500
    
    data = request.get_json()
    
    if not data or 'question' not in data:
        return jsonify({'error': 'No question provided'}), 400
    
    question = data['question'].strip()
    
    if not question:
        return jsonify({'error': 'Question cannot be empty'}), 400
    
    try:
        result = rag_agent.query(question, top_k=5)
        return jsonify({
            'success': True,
            'data': result
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


@app.route('/api/stats', methods=['GET'])
def get_statistics():
    """Get knowledge base statistics"""
    if not rag_agent:
        return jsonify({'error': 'RAG Agent not initialized'}), 500
    
    try:
        stats = rag_agent.get_stats()
        return jsonify({
            'success': True,
            'data': stats
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/clear', methods=['POST'])
def clear_knowledge_base():
    """Clear the knowledge base"""
    if not rag_agent:
        return jsonify({'error': 'RAG Agent not initialized'}), 500
    
    try:
        rag_agent.clear_knowledge_base()
        return jsonify({
            'success': True,
            'message': 'Knowledge base cleared successfully'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


if __name__ == '__main__':
    print("\n" + "="*70)
    print("🚀 ULTRA-ADVANCED RAG WEB APPLICATION")
    print("="*70)
    print("📁 Supported formats: PDF, DOCX, TXT")
    print("🤖 Powered by: Google Gemini AI")
    print("🌐 Web Interface: http://localhost:5000")
    print("="*70 + "\n")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
