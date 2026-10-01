/**
 * Client-Side Privacy Masking Library
 * 
 * Masks PII, PCI, HIPAA, and SOX compliance data before sending to backend.
 * No expensive mobile AI models needed - uses regex patterns and rules.
 * 
 * Usage:
 *   const masker = new PrivacyMasker();
 *   const { maskedText, tokens } = masker.maskText(originalText);
 *   // Send maskedText to backend
 *   // Store tokens locally for unmasking
 *   const unmasked = masker.unmaskText(maskedText, tokens);
 */

export interface MaskToken {
  id: string;
  type: 'name' | 'ssn' | 'account' | 'card' | 'phone' | 'email' | 'address' | 'dob' | 'medical_id' | 'health_insurance';
  originalValue: string;
  maskedValue: string;
}

export interface MaskResult {
  maskedText: string;
  tokens: MaskToken[];
  hasPersonalData: boolean;
}

export class PrivacyMasker {
  private tokenCounter: number = 0;
  
  /**
   * Mask sensitive data in text
   */
  maskText(text: string): MaskResult {
    let maskedText = text;
    const tokens: MaskToken[] = [];
    
    // 1. Mask Social Security Numbers (SSN)
    const ssnPattern = /\b\d{3}-\d{2}-\d{4}\b|\b\d{9}\b/g;
    maskedText = this.maskPattern(maskedText, ssnPattern, 'ssn', tokens);
    
    // 2. Mask Credit Card Numbers
    const cardPattern = /\b(?:\d{4}[-\s]?){3}\d{4}\b/g;
    maskedText = this.maskPattern(maskedText, cardPattern, 'card', tokens);
    
    // 3. Mask Bank Account Numbers (8-17 digits)
    const accountPattern = /\b\d{8,17}\b/g;
    maskedText = this.maskPattern(maskedText, accountPattern, 'account', tokens);
    
    // 4. Mask Phone Numbers
    const phonePattern = /\b(?:\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})\b/g;
    maskedText = this.maskPattern(maskedText, phonePattern, 'phone', tokens);
    
    // 5. Mask Email Addresses
    const emailPattern = /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/g;
    maskedText = this.maskPattern(maskedText, emailPattern, 'email', tokens);
    
    // 6. Mask Dates of Birth (various formats)
    const dobPattern = /\b(?:0?[1-9]|1[0-2])[-/](?:0?[1-9]|[12][0-9]|3[01])[-/](?:19|20)\d{2}\b/g;
    maskedText = this.maskPattern(maskedText, dobPattern, 'dob', tokens);
    
    // 7. Mask Medical Record Numbers (MRN)
    const mrnPattern = /\b(?:MRN|Medical Record|Patient ID)[\s:]*([A-Z0-9]{6,12})\b/gi;
    maskedText = this.maskPattern(maskedText, mrnPattern, 'medical_id', tokens);
    
    // 8. Mask Health Insurance IDs
    const insurancePattern = /\b(?:Insurance|Policy|Member)[\s#:]*([A-Z0-9]{8,15})\b/gi;
    maskedText = this.maskPattern(maskedText, insurancePattern, 'health_insurance', tokens);
    
    // 9. Mask Names (common patterns - this is heuristic)
    // Look for capitalized words that appear to be names
    const namePattern = /\b([A-Z][a-z]+(?:\s[A-Z][a-z]+){1,3})\b/g;
    maskedText = this.maskNamePattern(maskedText, namePattern, tokens);
    
    // 10. Mask Street Addresses
    const addressPattern = /\b\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct|Circle|Cir|Way)\b/gi;
    maskedText = this.maskPattern(maskedText, addressPattern, 'address', tokens);
    
    return {
      maskedText,
      tokens,
      hasPersonalData: tokens.length > 0
    };
  }
  
  /**
   * Unmask text using stored tokens
   */
  unmaskText(maskedText: string, tokens: MaskToken[]): string {
    let unmaskedText = maskedText;
    
    // Replace masked tokens with original values
    for (const token of tokens) {
      unmaskedText = unmaskedText.replace(
        new RegExp(this.escapeRegex(token.maskedValue), 'g'),
        token.originalValue
      );
    }
    
    return unmaskedText;
  }
  
  /**
   * Mask financial amounts (optional - for extra privacy)
   */
  maskAmounts(text: string): MaskResult {
    const tokens: MaskToken[] = [];
    let maskedText = text;
    
    // Mask dollar amounts
    const amountPattern = /\$[\d,]+\.?\d*/g;
    maskedText = this.maskPattern(maskedText, amountPattern, 'account', tokens);
    
    return {
      maskedText,
      tokens,
      hasPersonalData: tokens.length > 0
    };
  }
  
  /**
   * Validate if text contains sensitive data
   */
  containsSensitiveData(text: string): boolean {
    const result = this.maskText(text);
    return result.hasPersonalData;
  }
  
  /**
   * Get statistics about masked data
   */
  getMaskingStats(tokens: MaskToken[]): Record<string, number> {
    const stats: Record<string, number> = {};
    
    for (const token of tokens) {
      stats[token.type] = (stats[token.type] || 0) + 1;
    }
    
    return stats;
  }
  
  // Private helper methods
  
  private maskPattern(
    text: string,
    pattern: RegExp,
    type: MaskToken['type'],
    tokens: MaskToken[]
  ): string {
    return text.replace(pattern, (match) => {
      const tokenId = `[${type.toUpperCase()}_${++this.tokenCounter}]`;
      
      tokens.push({
        id: tokenId,
        type,
        originalValue: match,
        maskedValue: tokenId
      });
      
      return tokenId;
    });
  }
  
  private maskNamePattern(
    text: string,
    pattern: RegExp,
    tokens: MaskToken[]
  ): string {
    // Only mask names that appear multiple times or in specific contexts
    const matches = text.match(pattern) || [];
    const nameCounts = new Map<string, number>();
    
    for (const match of matches) {
      nameCounts.set(match, (nameCounts.get(match) || 0) + 1);
    }
    
    // Mask names that appear more than once (likely real names)
    let maskedText = text;
    for (const [name, count] of nameCounts.entries()) {
      if (count > 1 || this.isLikelyName(name)) {
        const tokenId = `[NAME_${++this.tokenCounter}]`;
        
        tokens.push({
          id: tokenId,
          type: 'name',
          originalValue: name,
          maskedValue: tokenId
        });
        
        maskedText = maskedText.replace(
          new RegExp(this.escapeRegex(name), 'g'),
          tokenId
        );
      }
    }
    
    return maskedText;
  }
  
  private isLikelyName(text: string): boolean {
    // Heuristics to determine if text is likely a name
    const words = text.split(/\s+/);
    
    // Names typically have 2-4 words
    if (words.length < 2 || words.length > 4) return false;
    
    // All words should be capitalized
    if (!words.every(w => /^[A-Z][a-z]+$/.test(w))) return false;
    
    // Common name indicators
    const nameIndicators = ['Dr', 'Mr', 'Mrs', 'Ms', 'Miss'];
    if (nameIndicators.some(ind => text.startsWith(ind))) return true;
    
    return true;
  }
  
  private escapeRegex(str: string): string {
    return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }
}

/**
 * React Hook for privacy masking
 */
export function usePrivacyMasking() {
  const masker = new PrivacyMasker();
  
  const maskData = (text: string) => {
    return masker.maskText(text);
  };
  
  const unmaskData = (maskedText: string, tokens: MaskToken[]) => {
    return masker.unmaskText(maskedText, tokens);
  };
  
  const checkSensitiveData = (text: string) => {
    return masker.containsSensitiveData(text);
  };
  
  return {
    maskData,
    unmaskData,
    checkSensitiveData,
    masker
  };
}

/**
 * Example Usage:
 * 
 * // In your React component
 * const { maskData, unmaskData } = usePrivacyMasking();
 * 
 * // When uploading a document
 * const fileContent = await readFile(file);
 * const { maskedText, tokens } = maskData(fileContent);
 * 
 * // Store tokens locally (encrypted)
 * localStorage.setItem(`tokens_${fileId}`, JSON.stringify(tokens));
 * 
 * // Send only masked data to backend
 * await uploadDocument(maskedText);
 * 
 * // When displaying results
 * const response = await getAnalysis(fileId);
 * const tokens = JSON.parse(localStorage.getItem(`tokens_${fileId}`));
 * const unmaskedResponse = unmaskData(response.text, tokens);
 */

export default PrivacyMasker;
