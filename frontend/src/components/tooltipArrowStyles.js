/**
 * Arrow (caret) positioning styles for tooltip panel, keyed by placement direction.
 */
const BORDER = '1px solid rgba(34,211,238,0.2)'
const BASE = { background: 'rgba(10,20,30,0.92)' }

export const arrowStyles = {
  top: {
    ...BASE,
    bottom: '-3px',
    left: '50%',
    transform: 'translateX(-50%) rotate(45deg)',
    borderRight: BORDER,
    borderBottom: BORDER,
  },
  bottom: {
    ...BASE,
    top: '-3px',
    left: '50%',
    transform: 'translateX(-50%) rotate(45deg)',
    borderLeft: BORDER,
    borderTop: BORDER,
  },
  left: {
    ...BASE,
    right: '-3px',
    top: '50%',
    transform: 'translateY(-50%) rotate(45deg)',
    borderTop: BORDER,
    borderRight: BORDER,
  },
  right: {
    ...BASE,
    left: '-3px',
    top: '50%',
    transform: 'translateY(-50%) rotate(45deg)',
    borderBottom: BORDER,
    borderLeft: BORDER,
  },
}

export const panelBaseStyle = {
  background: 'rgba(10,20,30,0.92)',
  border: '1px solid rgba(34,211,238,0.2)',
  boxShadow: '0 10px 40px rgba(8,47,73,0.3)',
}

export const dividerStyle = { borderTop: '1px solid rgba(34,211,238,0.1)' }

export const calcLabelColor = 'rgba(34,211,238,0.6)'
