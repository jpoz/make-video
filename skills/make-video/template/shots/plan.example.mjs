// Copy to shots/plan.mjs and edit. One step = one screenshot + the boxes of the elements the film points at.
// Use stable selectors (roles, labels, test ids). If the app needs a login or data, use a local build
// with stub API answers (page.route) so every capture is the same.
export default {
  url: 'http://localhost:3000/',
  viewport: { width: 1600, height: 900 },
  dark: false,
  async setup(page) {
    await page.waitForLoadState('networkidle');
  },
  steps: [
    { name: '01-home', boxes: { newButton: 'role=button[name="New"]', search: 'input[type=search]' } },
    {
      name: '02-dialog',
      actions: async page => { await page.click('role=button[name="New"]'); },
      boxes: { dialog: 'role=dialog', save: 'role=button[name="Save"]' },
    },
    {
      name: '03-typed',
      actions: async page => { await page.fill('role=dialog >> input', 'Quarterly report'); },
      boxes: { field: 'role=dialog >> input', save: 'role=button[name="Save"]' },
    },
  ],
};
