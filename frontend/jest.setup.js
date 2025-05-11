// Learn more: https://github.com/testing-library/jest-dom
import '@testing-library/jest-dom';

jest.mock('next/router', () => ({
  useRouter: () => ({
    push: jest.fn(),
    replace: jest.fn(),
    prefetch: jest.fn(),
    back: jest.fn(),
    pathname: '/',
    query: {},
  }),
}));

process.env = {
  ...process.env,
  NEXT_PUBLIC_API_URL: 'http://localhost:8000',
}; 