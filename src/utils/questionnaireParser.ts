import { Question, Questionnaire, QuestionnaireSection } from '../types/schema';
import { QuestionType, StudyPhase } from '../types/enums';

export interface CSVRow {
  'Question Type': string;
  'Question Text': string;
  'Choices': string;
  'Question Name'?: string;
  'Scoring'?: string;
  'Block'?: string;
}

/**
 * Parse CSV questionnaire data into structured questionnaire objects
 */
export class QuestionnaireParser {
  
  /**
   * Parse CSV text into questionnaire objects
   */
  static parseCSV(csvText: string): Questionnaire[] {
    const lines = csvText.split('\n').filter(line => 
      line.trim() && 
      !line.trim().startsWith('#') && 
      !line.trim().startsWith('##')
    );
    
    if (lines.length === 0) return [];
    
    const headers = this.parseCSVLine(lines[0]);
    const rows: CSVRow[] = lines.slice(1).map(line => {
      const values = this.parseCSVLine(line);
      const row: any = {};
      headers.forEach((header, index) => {
        row[header] = values[index] || '';
      });
      return row as CSVRow;
    });

    return this.groupIntoQuestionnaires(rows);
  }

  /**
   * Parse a single CSV line, handling quoted values properly
   */
  private static parseCSVLine(line: string): string[] {
    const result: string[] = [];
    let current = '';
    let inQuotes = false;
    
    for (let i = 0; i < line.length; i++) {
      const char = line[i];
      
      if (char === '"') {
        if (inQuotes && line[i + 1] === '"') {
          // Handle escaped quotes
          current += '"';
          i++; // Skip next quote
        } else {
          inQuotes = !inQuotes;
        }
      } else if (char === ',' && !inQuotes) {
        result.push(current.trim());
        current = '';
      } else {
        current += char;
      }
    }
    
    result.push(current.trim());
    return result;
  }

  /**
   * Group CSV rows into questionnaire objects based on phase detection
   */
  private static groupIntoQuestionnaires(rows: CSVRow[]): Questionnaire[] {
    const questionnaires: Questionnaire[] = [];
    let currentPhase: StudyPhase = StudyPhase.PRE_GAME;
    let currentQuestions: Question[] = [];
    let questionCounter = 0;

    for (const row of rows) {
      // Detect phase transitions based on Block field or question patterns
      const newPhase = this.detectPhase(row, currentPhase);
      
      if (newPhase !== currentPhase && currentQuestions.length > 0) {
        // Create questionnaire for previous phase
        questionnaires.push(this.createQuestionnaire(currentPhase, currentQuestions));
        currentQuestions = [];
        questionCounter = 0;
      }
      
      currentPhase = newPhase;
      
      // Convert row to question
      const question = this.convertRowToQuestion(row, questionCounter++);
      if (question) {
        currentQuestions.push(question);
      }
    }

    // Add final questionnaire
    if (currentQuestions.length > 0) {
      questionnaires.push(this.createQuestionnaire(currentPhase, currentQuestions));
    }

    return questionnaires;
  }

  /**
   * Detect which study phase this question belongs to
   */
  private static detectPhase(row: CSVRow, currentPhase: StudyPhase): StudyPhase {
    const block = row.Block?.toLowerCase() || '';
    const questionText = row['Question Text'].toLowerCase();
    
    if (block.includes('session 1') || questionText.includes('session 1')) {
      return StudyPhase.SESSION_1;
    }
    if (block.includes('session 2') || questionText.includes('session 2')) {
      return StudyPhase.SESSION_2;
    }
    if (block.includes('final') || block.includes('compare') || questionText.includes('both sessions')) {
      return StudyPhase.FINAL_COMPARE;
    }
    
    // Default to pre-game for initial questions
    return currentPhase === StudyPhase.PRE_GAME ? StudyPhase.PRE_GAME : currentPhase;
  }

  /**
   * Convert CSV row to Question object
   */
  private static convertRowToQuestion(row: CSVRow, index: number): Question | null {
    const type = this.parseQuestionType(row['Question Type']);
    const text = row['Question Text'];
    
    if (!text || type === null) return null;

    const choices = row.Choices ? 
      row.Choices.split(/[,|]/).map(choice => choice.trim()).filter(Boolean) : 
      undefined;

    return {
      id: `q${index + 1}`,
      type,
      text,
      choices,
      required: type !== QuestionType.BLOCK_HEADER,
      questionName: row['Question Name'],
      scoring: row.Scoring,
      block: row.Block
    };
  }

  /**
   * Parse question type from CSV
   */
  private static parseQuestionType(typeStr: string): QuestionType | null {
    switch (typeStr?.toUpperCase()) {
      case 'MC': return QuestionType.MULTIPLE_CHOICE;
      case 'TE': return QuestionType.TEXT_ENTRY;
      case 'BLOCK': return QuestionType.BLOCK_HEADER;
      default: return null;
    }
  }

  /**
   * Create a questionnaire object for a phase
   */
  private static createQuestionnaire(phase: StudyPhase, questions: Question[]): Questionnaire {
    const titles = {
      [StudyPhase.PRE_GAME]: 'Pre-Study Questionnaire',
      [StudyPhase.SESSION_1]: 'Session 1 Feedback',
      [StudyPhase.SESSION_2]: 'Session 2 Feedback', 
      [StudyPhase.FINAL_COMPARE]: 'Final Comparison Survey',
      [StudyPhase.COMPLETED]: 'Study Complete'
    };

    const descriptions = {
      [StudyPhase.PRE_GAME]: 'Please answer these questions before beginning the study.',
      [StudyPhase.SESSION_1]: 'Thank you for completing Session 1. Please share your initial impressions.',
      [StudyPhase.SESSION_2]: 'Thank you for completing Session 2. Please reflect on this session.',
      [StudyPhase.FINAL_COMPARE]: 'Please compare your experiences across both sessions.',
      [StudyPhase.COMPLETED]: 'Study completed successfully.'
    };

    // Group questions into sections based on block headers
    const sections = this.groupQuestionsIntoSections(questions);

    return {
      id: `questionnaire_${phase}`,
      title: titles[phase],
      description: descriptions[phase],
      phase,
      sections,
      required: true
    };
  }

  /**
   * Group questions into sections based on block headers
   */
  private static groupQuestionsIntoSections(questions: Question[]): QuestionnaireSection[] {
    const sections: QuestionnaireSection[] = [];
    let currentSection: QuestionnaireSection | null = null;
    let sectionCounter = 0;

    for (const question of questions) {
      if (question.type === QuestionType.BLOCK_HEADER) {
        // Start new section
        if (currentSection) {
          sections.push(currentSection);
        }
        currentSection = {
          id: `section_${sectionCounter++}`,
          title: question.text.replace(/^##\s*/, '').replace(/\s*##$/, ''),
          questions: []
        };
      } else if (currentSection) {
        currentSection.questions.push(question);
      } else {
        // Create default section if no block header found
        currentSection = {
          id: `section_${sectionCounter++}`,
          title: 'Questions',
          questions: [question]
        };
      }
    }

    if (currentSection) {
      sections.push(currentSection);
    }

    return sections.filter(section => section.questions.length > 0);
  }
}

/**
 * Load questionnaires from the project's CSV files
 */
export async function loadQuestionnaireFromCSV(): Promise<Questionnaire[]> {
  // Prefer the split files in /public for consistency across phases
  const questionnaires: Questionnaire[] = [];
  const files = [
    'questionnaire_pre_game.csv',
    'questionnaire_session_1.csv',
    'questionnaire_session_2.csv', 
    'questionnaire_final_compare.csv'
  ];

  try {
    for (const file of files) {
      try {
        const response = await fetch(`/${file}`);
        if (!response.ok) continue;
        const csvText = await response.text();
        const parsed = QuestionnaireParser.parseCSV(csvText);
        if (parsed.length > 0) questionnaires.push(...parsed);
      } catch {/* ignore individual file errors */}
    }

    if (questionnaires.length > 0) return questionnaires;
  } catch (e) {
    console.warn('Error loading split questionnaire CSVs:', e);
  }

  // Fallback to consolidated CSV at repo root if split files not found
  try {
    const resp = await fetch('/questionarrie.csv');
    if (resp.ok) {
      const csvText = await resp.text();
      const parsed = QuestionnaireParser.parseCSV(csvText);
      if (parsed.length > 0) return parsed;
    } else {
      console.warn('questionarrie.csv not found at root:', resp.statusText);
    }
  } catch (e) {
    console.warn('Error loading questionarrie.csv:', e);
  }

  return questionnaires;
}
