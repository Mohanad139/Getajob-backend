// Parse API error response to get a readable message
export const parseError = (error) => {
  const detail = error.response?.data?.detail;

  if (!detail) {
    return error.message || 'An unexpected error occurred';
  }

  // If detail is a string, return it directly
  if (typeof detail === 'string') {
    return detail;
  }

  // If detail is an array (Pydantic validation errors), parse it
  if (Array.isArray(detail)) {
    return detail.map(err => {
      if (typeof err === 'string') return err;
      // Pydantic error format: {type, loc, msg, input, ctx}
      const field = err.loc ? err.loc.slice(1).join('.') : '';
      return field ? `${field}: ${err.msg}` : err.msg;
    }).join(', ');
  }

  // If detail is an object with a message property
  if (detail.msg || detail.message) {
    return detail.msg || detail.message;
  }

  return 'An unexpected error occurred';
};
