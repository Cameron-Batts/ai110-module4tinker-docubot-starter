"""
Core DocuBot class responsible for:
- Loading documents from the docs/ folder
- Building a simple retrieval index (Phase 1)
- Retrieving relevant snippets (Phase 1)
- Supporting retrieval only answers
- Supporting RAG answers when paired with Gemini (Phase 2)
"""

import os
import glob
import re

class DocuBot:
    def __init__(self, docs_folder="docs", llm_client=None):
        """
        docs_folder: directory containing project documentation files
        llm_client: optional Gemini client for LLM based answers
        """
        self.docs_folder = docs_folder
        self.llm_client = llm_client

        # Load documents into memory
        self.documents = self.load_documents()  # List of (filename, text)

        # Build a retrieval index (implemented in Phase 1)
        self.index = self.build_index(self.documents)

    # -----------------------------------------------------------
    # Document Loading
    # -----------------------------------------------------------

    def load_documents(self):
        """
        Loads all .md and .txt files inside docs_folder.
        Returns a list of tuples: (filename, text)
        """
        docs = []
        pattern = os.path.join(self.docs_folder, "*.*")
        for path in glob.glob(pattern):
            if path.endswith(".md") or path.endswith(".txt"):
                with open(path, "r", encoding="utf8") as f:
                    text = f.read()
                filename = os.path.basename(path)
                docs.append((filename, text))
        return docs

    # -----------------------------------------------------------
    # Index Construction (Phase 1)
    # -----------------------------------------------------------

    def tokenize(self, text):
        """Extract lowercase keywords and remove common question words."""
        stop_words = {
            "a", "an", "the", "is", "are", "was", "were", "be",
            "where", "what", "which", "how", "when", "why",
            "do", "does", "did", "i", "you", "we", "it",
            "to", "of", "in", "on", "for", "from", "with",
            "and", "or", "by", "as", "at", "this", "that",
            "these", "those", "there", "any", "all", "can",
            "my", "our", "your", "me", "about", "mention",
            "docs", "documentation"
        }
        words = re.findall(r"[a-z0-9]+", text.lower())
        return {word for word in words if word not in stop_words}

    def build_index(self, documents):
        """Map each keyword to the filenames containing it."""
        index = {}
        for filename, text in documents:
            for word in self.tokenize(text):
                index.setdefault(word, set()).add(filename)
        return index

    def score_document(self, query, text):
        """Return the fraction of query keywords found in the text."""
        query_words = self.tokenize(query)
        if not query_words:
            return 0.0

        text_words = self.tokenize(text)
        matches = query_words & text_words
        return len(matches) / len(query_words)

    def retrieve(self, query, top_k=3):
        """Rank Markdown sections and reject weak keyword matches."""
        if top_k <= 0:
            return []

        candidate_files = set()
        for word in self.tokenize(query):
            candidate_files.update(self.index.get(word, set()))

        scored = []
        for filename, text in self.documents:
            if filename not in candidate_files:
                continue

            # Keep each heading with its following paragraphs and examples.
            sections = re.split(r"\n(?=#{1,3} )", text)
            for section in sections:
                section = section.strip()
                if not section:
                    continue

                score = self.score_document(query, section)
                if score >= 0.3:
                    scored.append((filename, section, score))

        scored = sorted(scored, key=lambda item: item[2], reverse=True)
        return [(filename, section) for filename, section, _ in scored[:top_k]]

    def answer_retrieval_only(self, query, top_k=3):
        """
        Phase 1 retrieval only mode.
        Returns raw snippets and filenames with no LLM involved.
        """
        snippets = self.retrieve(query, top_k=top_k)

        if not snippets:
            return "I do not know based on these docs."

        formatted = []
        for filename, text in snippets:
            formatted.append(f"[{filename}]\n{text}\n")

        return "\n---\n".join(formatted)

    def answer_rag(self, query, top_k=3):
        """
        Phase 2 RAG mode.
        Uses student retrieval to select snippets, then asks Gemini
        to generate an answer using only those snippets.
        """
        if self.llm_client is None:
            raise RuntimeError(
                "RAG mode requires an LLM client. Provide a GeminiClient instance."
            )

        snippets = self.retrieve(query, top_k=top_k)

        if not snippets:
            return "I do not know based on these docs."

        return self.llm_client.answer_from_snippets(query, snippets)

    # -----------------------------------------------------------
    # Bonus Helper: concatenated docs for naive generation mode
    # -----------------------------------------------------------

    def full_corpus_text(self):
        """
        Returns all documents concatenated into a single string.
        This is used in Phase 0 for naive 'generation only' baselines.
        """
        return "\n\n".join(text for _, text in self.documents)
