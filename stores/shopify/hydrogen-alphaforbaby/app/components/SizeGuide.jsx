import { useState } from 'react';
import { Dialog, DialogHeader, DialogBody, Button, ButtonGroup } from '@material-tailwind/react';
import { useDialog } from '../hooks/useDialog';

// Universal baby/toddler sizing reference — same on every product page (CJ doesn't
// provide girth/waist/hips per product, only height/age sometimes). Values in cm/kg;
// inches/lb are derived on the fly for the unit toggle.
const CHART_CM = [
  {size: '5lb Newborn', height: 44, weight: 2.3, chest: null, waist: null, hip: null},
  {size: 'Newborn', height: 50, weight: 3.4, chest: 38, waist: 40, hip: 42},
  {size: '0-1 Month', height: 56, weight: 4.5, chest: null, waist: 42, hip: 44},
  {size: '1-3 Months', height: 62, weight: 5.5, chest: 41, waist: 44, hip: 46},
  {size: '3-6 Months', height: 68, weight: 7, chest: 43, waist: 46, hip: 48},
  {size: '6-9 Months', height: 74, weight: 9, chest: 45, waist: 48, hip: 50},
  {size: '9-12 Months', height: 80, weight: 10.5, chest: 47, waist: 49, hip: 51},
  {size: '12-18 Months', height: 86, weight: 11.5, chest: 49, waist: 50, hip: 52},
  {size: '18-24 Months', height: 92, weight: 12.5, chest: 51, waist: 52, hip: 54},
  {size: '2-3 Years', height: 98, weight: 14, chest: 53, waist: 53, hip: 55},
  // Older kids — from the Age/EU-cm/US-size conversion chart (no weight/chest/
  // waist/hip data available for these from CJ, so left blank rather than guessed).
  {size: '3-4 Years', height: 104, weight: null, chest: null, waist: null, hip: null},
  {size: '4-5 Years', height: 110, weight: null, chest: null, waist: null, hip: null},
  {size: '5-6 Years', height: 116, weight: null, chest: null, waist: null, hip: null},
  {size: '6-7 Years', height: 122, weight: null, chest: null, waist: null, hip: null},
  {size: '7-8 Years', height: 128, weight: null, chest: null, waist: null, hip: null},
  {size: '8-9 Years', height: 134, weight: null, chest: null, waist: null, hip: null},
  {size: '9-10 Years', height: 140, weight: null, chest: null, waist: null, hip: null},
  {size: '10-11 Years', height: 146, weight: null, chest: null, waist: null, hip: null},
  {size: '11-12 Years', height: 152, weight: null, chest: null, waist: null, hip: null},
  {size: '12-13 Years', height: 158, weight: null, chest: null, waist: null, hip: null},
  {size: '13-14 Years', height: 164, weight: null, chest: null, waist: null, hip: null},
  {size: '14-15 Years', height: 170, weight: null, chest: null, waist: null, hip: null},
];

function cmToIn(cm) {
  return cm == null ? null : Math.round((cm / 2.54) * 4) / 4;
}
function kgToLb(kg) {
  return kg == null ? null : Math.round(kg * 2.20462 * 10) / 10;
}
function fmt(v) {
  return v == null ? '–' : v;
}

export function SizeGuide() {
  const { open, openDialog, closeDialog, handler } = useDialog();
  const [unit, setUnit] = useState('cm');

  return (
    <>
      <button type="button" className="size-guide-trigger" onClick={openDialog}>
        Size Guide
      </button>
      {open && (
        <Dialog open={open} handler={handler} className="size-guide-dialog" size="md">
          <DialogHeader className="size-guide-header">
            <h3>Size Guide</h3>
            <button className="size-guide-close reset" onClick={closeDialog} aria-label="Close">&times;</button>
          </DialogHeader>
          <DialogBody className="size-guide-body">
            <ButtonGroup variant="outlined" color="gray" className="size-guide-unit-toggle">
              {/* ButtonGroup clones children and OVERRIDES their variant/color with its own
                  (see node_modules/@material-tailwind/react/components/ButtonGroup) — only
                  className survives per-child, so that's how the active segment is marked. */}
              <Button
                className={unit === 'in' ? 'size-guide-toggle-active' : ''}
                onClick={() => setUnit('in')}
              >
                Inches
              </Button>
              <Button
                className={unit === 'cm' ? 'size-guide-toggle-active' : ''}
                onClick={() => setUnit('cm')}
              >
                CM
              </Button>
            </ButtonGroup>

            <div className="size-guide-table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Size</th>
                    <th>Height ({unit})</th>
                    <th>Weight ({unit === 'cm' ? 'kg' : 'lb'})</th>
                    <th>Chest ({unit})</th>
                    <th>Waist ({unit})</th>
                    <th>Hip ({unit})</th>
                  </tr>
                </thead>
                <tbody>
                  {CHART_CM.map((row) => (
                    <tr key={row.size}>
                      <td>{row.size}</td>
                      <td>{unit === 'cm' ? row.height : fmt(cmToIn(row.height))}</td>
                      <td>{unit === 'cm' ? fmt(row.weight) : fmt(kgToLb(row.weight))}</td>
                      <td>{unit === 'cm' ? fmt(row.chest) : fmt(cmToIn(row.chest))}</td>
                      <td>{unit === 'cm' ? fmt(row.waist) : fmt(cmToIn(row.waist))}</td>
                      <td>{unit === 'cm' ? fmt(row.hip) : fmt(cmToIn(row.hip))}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="size-guide-howto">
              <h4>How to measure</h4>
              <ol>
                <li><b>Height:</b> Lay baby flat on their back, feet together, and measure from the top of the head to the heel.</li>
                <li><b>Chest:</b> Wrap the tape under the arms, around the fullest part of the chest.</li>
                <li><b>Waist:</b> Measure around the natural waistline, just above the belly button.</li>
                <li><b>Hip:</b> Measure around the fullest part of the hips.</li>
              </ol>
            </div>
          </DialogBody>
        </Dialog>
      )}
    </>
  );
}
