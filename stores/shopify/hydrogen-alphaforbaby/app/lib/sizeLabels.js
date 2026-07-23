export function normalizeSizeLabel(raw) {
  const match = raw.match(/^(\d+)cm$/);
  if (!match) return raw;
  
  const cm = parseInt(match[1], 10);
  
  // Matches the Size Guide table's own buckets exactly (SizeGuide.jsx's CHART_CM),
  // so the size buttons and the size chart always agree on wording.
  if (cm <= 44) return '5lb Newborn';
  if (cm <= 50) return 'Newborn';
  if (cm <= 56) return '0-1 Month';
  if (cm <= 62) return '1-3 Months';
  if (cm <= 68) return '3-6 Months';
  if (cm <= 74) return '6-9 Months';
  if (cm <= 80) return '9-12 Months';
  if (cm <= 86) return '12-18 Months';
  if (cm <= 92) return '18-24 Months';
  if (cm <= 98) return '2-3 Years';
  // Beyond toddler sizes — matches the Age/EU-cm/US-size conversion chart.
  if (cm <= 104) return '3-4 Years';
  if (cm <= 110) return '4-5 Years';
  if (cm <= 116) return '5-6 Years';
  if (cm <= 122) return '6-7 Years';
  if (cm <= 128) return '7-8 Years';
  if (cm <= 134) return '8-9 Years';
  if (cm <= 140) return '9-10 Years';
  if (cm <= 146) return '10-11 Years';
  // Continuing the same 6cm-per-year progression for bigger kids.
  if (cm <= 152) return '11-12 Years';
  if (cm <= 158) return '12-13 Years';
  if (cm <= 164) return '13-14 Years';
  if (cm <= 170) return '14-15 Years';

  return raw;
}

export function getDisplaySizeLabels(rawValues) {
  const labelMap = new Map();
  
  for (const raw of rawValues) {
    const label = normalizeSizeLabel(raw);
    
    // If two different raw values would map to same label,
    // return raw values unchanged to avoid ambiguous duplicates
    if (labelMap.has(label) && labelMap.get(label) !== raw) {
      return new Map(rawValues.map(v => [v, v]));
    }
    
    labelMap.set(label, raw);
  }
  
  return new Map([...labelMap.entries()].map(([label, raw]) => [raw, label]));
}