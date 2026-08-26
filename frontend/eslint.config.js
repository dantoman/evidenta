import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import tseslint from 'typescript-eslint'

export default tseslint.config(
  { ignores: ['dist', 'node_modules'] },
  {
    files: ['**/*.{ts,tsx}'],
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    languageOptions: {
      ecmaVersion: 2023,
      globals: globals.browser,
    },
    plugins: {
      'react-hooks': reactHooks,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,

      // C16. The only entry points for grids are DataGrid and EntryGrid. A
      // screen that reaches for react-table directly is how a third grid gets
      // built without anybody deciding to build one (ADR-001).
      //
      // The exception lives in an override below, for the two component files
      // themselves -- named there so it stays an exception.
      'no-restricted-imports': [
        'error',
        {
          paths: [
            {
              name: '@tanstack/react-table',
              message:
                'C16: screens use DataGrid or EntryGrid from @/shared. Only those two files import react-table (ADR-001).',
            },
          ],
        },
      ],
    },
  },
  {
    // The two grid components. Listed by path so adding a third would be a
    // visible edit here rather than a quiet import somewhere.
    files: ['src/shared/DataGrid/**', 'src/shared/EntryGrid/**'],
    rules: {
      'no-restricted-imports': 'off',

      // C21 / ADR-042. Row height and cell padding come from the density tokens.
      // A literal here would opt one grid out of the scale silently, and the
      // scale exists precisely because compressing forty screens later is a
      // rewrite rather than an adjustment.
      //
      // Scoped to the two grid files on purpose, and the scope is the honest
      // one: they are the only place that sets a row height at all. A screen
      // never does -- it hands rows to the grid. This rule therefore covers
      // where the scale can actually be defeated, not everywhere spacing is
      // written.
      'no-restricted-syntax': [
        'error',
        {
          selector:
            'Literal[value=/\\b(h|min-h|max-h|py|pt|pb)-(\\d|\\[)/]',
          message:
            'C21: row height and cell padding come from the density tokens in index.css (ADR-042), never from a literal utility.',
        },
        {
          selector: 'TemplateElement[value.raw=/\\b(h|min-h|max-h|py|pt|pb)-(\\d|\\[)/]',
          message:
            'C21: row height and cell padding come from the density tokens in index.css (ADR-042), never from a literal utility.',
        },
      ],
    },
  },
)
