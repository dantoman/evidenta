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
    },
  },
)
