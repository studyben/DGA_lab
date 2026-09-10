const patterns: Record<string, string> = {
  '0': 'nnnwwnwnn', '1': 'wnnwnnnnw', '2': 'nnwwnnnnw',
  '3': 'wnwwnnnnn', '4': 'nnnwwnnnw', '5': 'wnnwwnnnn',
  '6': 'nnwwwnnnn', '7': 'nnnwnnwnw', '8': 'wnnwnnwnn',
  '9': 'nnwwnnwnn', 'A': 'wnnnnwnnw', 'B': 'nnwnnwnnw',
  'C': 'wnwnnwnnn', 'D': 'nnnnwwnnw', 'E': 'wnnnwwnnn',
  'F': 'nnwnwwnnn', 'G': 'nnnnnwwnw', 'H': 'wnnnnwwnn',
  'I': 'nnwnnwwnn', 'J': 'nnnnwwwnn', 'K': 'wnnnnnnww',
  'L': 'nnwnnnnww', 'M': 'wnwnnnnwn', 'N': 'nnnnwnnww',
  'O': 'wnnnwnnwn', 'P': 'nnwnwnnwn', 'Q': 'nnnnnnwww',
  'R': 'wnnnnnwwn', 'S': 'nnwnnnwwn', 'T': 'nnnnwnwwn',
  'U': 'wwnnnnnnw', 'V': 'nwwnnnnnw', 'W': 'wwwnnnnnn',
  'X': 'nwnnwnnnw', 'Y': 'wwnnwnnnn', 'Z': 'nwwnwnnnn',
  '-': 'nwnnnnwnw', '.': 'wwnnnnwnn', ' ': 'nwwnnnwnn',
  '$': 'nwnwnwnnn', '/': 'nwnwnnnwn', '+': 'nwnnnwnwn',
  '%': 'nnnwnwnwn', '*': 'nwnnwnwnn',
};


export function Code39Barcode({ value }: { value: string }) {
  const encoded = `*${value.toUpperCase()}*`;
  let cursor = 8;
  const bars: { x: number; width: number }[] = [];
  for (const character of encoded) {
    const pattern = patterns[character];
    if (!pattern) throw new Error(`Unsupported Code 39 character: ${character}`);
    [...pattern].forEach((widthCode, index) => {
      const width = widthCode === 'w' ? 5 : 2;
      if (index % 2 === 0) bars.push({ x: cursor, width });
      cursor += width;
    });
    cursor += 2;
  }
  return <svg className="barcode" viewBox={`0 0 ${cursor + 6} 76`}
    role="img" aria-label={`条码 ${value}`} preserveAspectRatio="none">
    <rect width={cursor + 6} height="76" fill="white" />
    {bars.map((bar, index) => <rect key={index} x={bar.x} y="4" width={bar.width} height="52" fill="#111827" />)}
    <text x={(cursor + 6) / 2} y="71" textAnchor="middle" fontSize="9" fontFamily="monospace">{value}</text>
  </svg>;
}
