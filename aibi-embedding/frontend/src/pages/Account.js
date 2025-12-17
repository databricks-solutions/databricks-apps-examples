// src/pages/Account.js
import React from 'react';
import { useAuth } from '../context/AuthContext';

const Account = () => {
  const { user } = useAuth();

  return (
    <div className="account-page">
      <h2>Account Information</h2>
      <p>Email: {user.email}</p>
      <p>Name: {user.name}</p>
      {/* Add more user information as needed */}
    </div>
  );
};

export default <Account/>;
