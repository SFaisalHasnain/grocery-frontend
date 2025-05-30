import React, { useState, useEffect } from "react";
import { BrowserRouter, Routes, Route, Navigate, Link, useNavigate, useLocation } from "react-router-dom";
import axios from "axios";
import { ToastContainer, toast } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import { Bar } from "react-chartjs-2";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
} from "chart.js";
import { FaHome, FaSearch, FaList, FaUserCircle, FaSignOutAlt, FaShoppingBasket, FaPoundSign, FaStore, FaUserAlt } from "react-icons/fa";
import "./App.css";

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend
);

// Home component
function Home() {
  const { user } = useAuth();
  
  return (
    <div className="min-h-screen bg-gray-100">
      <div className="container mx-auto px-4 py-8">
        <div className="bg-white rounded-lg shadow-lg overflow-hidden">
          <div className="bg-gradient-to-r from-indigo-500 to-purple-600 p-8 text-white">
            <h1 className="text-3xl font-bold mb-4">Welcome to UK Grocery Price Comparison</h1>
            <p className="text-xl">Find the best deals on groceries across top UK supermarkets</p>
          </div>
          
          <div className="p-6">
            <div className="grid md:grid-cols-3 gap-6 mb-8">
              <div className="bg-blue-50 p-6 rounded-lg shadow border border-blue-100">
                <div className="flex items-center justify-center h-12 w-12 rounded-md bg-blue-500 text-white mb-4">
                  <FaSearch className="text-xl" />
                </div>
                <h2 className="text-xl font-semibold mb-2">Search Products</h2>
                <p className="text-gray-600">Search for any grocery product and compare prices across top UK supermarkets.</p>
                <Link to="/search" className="mt-4 inline-block text-blue-500 hover:text-blue-700">
                  Start searching →
                </Link>
              </div>
              
              <div className="bg-green-50 p-6 rounded-lg shadow border border-green-100">
                <div className="flex items-center justify-center h-12 w-12 rounded-md bg-green-500 text-white mb-4">
                  <FaPoundSign className="text-xl" />
                </div>
                <h2 className="text-xl font-semibold mb-2">Save Money</h2>
                <p className="text-gray-600">Quickly see where products are cheapest and find the best deals.</p>
                <Link to="/search" className="mt-4 inline-block text-green-500 hover:text-green-700">
                  Find savings →
                </Link>
              </div>
              
              <div className="bg-purple-50 p-6 rounded-lg shadow border border-purple-100">
                <div className="flex items-center justify-center h-12 w-12 rounded-md bg-purple-500 text-white mb-4">
                  <FaList className="text-xl" />
                </div>
                <h2 className="text-xl font-semibold mb-2">Shopping Lists</h2>
                <p className="text-gray-600">Create and manage shopping lists to track your savings over time.</p>
                <Link to="/shopping-lists" className="mt-4 inline-block text-purple-500 hover:text-purple-700">
                  View lists →
                </Link>
              </div>
            </div>
            
            <div className="bg-gray-50 p-6 rounded-lg shadow-sm border border-gray-100 mb-8">
              <h2 className="text-2xl font-bold mb-4">How It Works</h2>
              <div className="grid md:grid-cols-3 gap-4">
                <div className="flex flex-col items-center text-center">
                  <div className="bg-indigo-100 rounded-full w-12 h-12 flex items-center justify-center text-indigo-500 text-xl font-bold mb-3">1</div>
                  <h3 className="font-semibold mb-1">Search for Products</h3>
                  <p className="text-gray-600 text-sm">Enter any grocery item you want to buy</p>
                </div>
                
                <div className="flex flex-col items-center text-center">
                  <div className="bg-indigo-100 rounded-full w-12 h-12 flex items-center justify-center text-indigo-500 text-xl font-bold mb-3">2</div>
                  <h3 className="font-semibold mb-1">Compare Prices</h3>
                  <p className="text-gray-600 text-sm">See prices from all major UK supermarkets</p>
                </div>
                
                <div className="flex flex-col items-center text-center">
                  <div className="bg-indigo-100 rounded-full w-12 h-12 flex items-center justify-center text-indigo-500 text-xl font-bold mb-3">3</div>
                  <h3 className="font-semibold mb-1">Save Money</h3>
                  <p className="text-gray-600 text-sm">Choose the cheapest option or build optimized shopping lists</p>
                </div>
              </div>
            </div>
            
            <div className="text-center mt-8">
              <Link to="/search" className="inline-block bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-3 px-6 rounded-lg shadow-md transition duration-300">
                Start Comparing Prices Now
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// Backend API URL from environment
const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Context for authentication
const AuthContext = React.createContext(null);

// Auth provider component
function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Check if user is logged in on mount
    const token = localStorage.getItem("token");
    if (token) {
      fetchUserProfile(token);
    } else {
      setLoading(false);
    }
  }, []);

  const fetchUserProfile = async (token) => {
    try {
      const response = await axios.get(`${API}/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setUser(response.data);
    } catch (error) {
      console.error("Error fetching user profile:", error);
      localStorage.removeItem("token");
    } finally {
      setLoading(false);
    }
  };

  const login = async (email, password) => {
    try {
      const formData = new FormData();
      formData.append("username", email);
      formData.append("password", password);

      const response = await axios.post(`${API}/login`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      const { access_token } = response.data;
      localStorage.setItem("token", access_token);
      
      // Fetch user profile with the new token
      const userResponse = await axios.get(`${API}/me`, {
        headers: { Authorization: `Bearer ${access_token}` },
      });
      
      // Set user state with the response data
      setUser(userResponse.data);
      
      return { success: true };
    } catch (error) {
      console.error("Login error:", error);
      return {
        success: false,
        message: error.response?.data?.detail || "Login failed",
      };
    }
  };

  const register = async (name, email, password) => {
    try {
      await axios.post(`${API}/register`, {
        name,
        email,
        password,
      });
      return { success: true };
    } catch (error) {
      console.error("Registration error:", error);
      return {
        success: false,
        message: error.response?.data?.detail || "Registration failed",
      };
    }
  };

  const logout = () => {
    localStorage.removeItem("token");
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{ user, login, logout, register, loading }}
    >
      {children}
    </AuthContext.Provider>
  );
}

// Hook to use auth context
function useAuth() {
  return React.useContext(AuthContext);
}

// Protected route component
function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (!loading && !user) {
      navigate("/login");
    }
  }, [user, loading, navigate]);

  if (loading) {
    return <div className="flex items-center justify-center h-screen">Loading...</div>;
  }

  return user ? children : null;
}

// Navigation component
function Navigation() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <nav className="bg-indigo-700 text-white shadow-lg">
      <div className="container mx-auto px-4">
        <div className="flex justify-between">
          <div className="flex space-x-4">
            <div className="flex items-center py-4">
              <Link to="/" className="flex items-center space-x-2">
                <FaShoppingBasket className="text-2xl" />
                <span className="font-bold text-xl">UK Grocery Compare</span>
              </Link>
            </div>
            {user ? (
              <div className="hidden md:flex items-center space-x-1">
                <Link to="/" className="py-4 px-3 hover:bg-indigo-600 flex items-center space-x-1">
                  <FaHome />
                  <span>Home</span>
                </Link>
                <Link to="/search" className="py-4 px-3 hover:bg-indigo-600 flex items-center space-x-1">
                  <FaSearch />
                  <span>Search</span>
                </Link>
                <Link to="/shopping-lists" className="py-4 px-3 hover:bg-indigo-600 flex items-center space-x-1">
                  <FaList />
                  <span>Shopping Lists</span>
                </Link>
                <Link to="/stores" className="py-4 px-3 hover:bg-indigo-600 flex items-center space-x-1">
                  <FaStore />
                  <span>Stores</span>
                </Link>
              </div>
            ) : (
              <div className="hidden md:flex items-center space-x-1">
                <Link to="/guest-search" className="py-4 px-3 hover:bg-indigo-600 flex items-center space-x-1">
                  <FaSearch />
                  <span>Search Products</span>
                </Link>
                <Link to="/stores" className="py-4 px-3 hover:bg-indigo-600 flex items-center space-x-1">
                  <FaStore />
                  <span>Stores</span>
                </Link>
              </div>
            )}
          </div>
          <div className="hidden md:flex items-center space-x-1">
            {user ? (
              <>
                <div className="py-4 px-3 flex items-center space-x-1">
                  <FaUserCircle />
                  <span>{user.name}</span>
                </div>
                <button
                  onClick={handleLogout}
                  className="py-2 px-3 bg-red-600 hover:bg-red-700 text-white rounded-md flex items-center space-x-1"
                >
                  <FaSignOutAlt />
                  <span>Logout</span>
                </button>
              </>
            ) : (
              <>
                <Link to="/login" className="py-2 px-3 bg-indigo-600 hover:bg-indigo-700 text-white rounded-md flex items-center space-x-1">
                  <FaUserAlt className="mr-1" />
                  <span>Login</span>
                </Link>
                <Link to="/register" className="py-2 px-3 bg-green-600 hover:bg-green-700 text-white rounded-md flex items-center space-x-1">
                  <span>Register</span>
                </Link>
              </>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
}

// Guest Search component
function GuestSearch() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);

  // Function to log data when searching - helpful for debugging
  const handleSearch = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;
    
    setLoading(true);
    // Clear previous results first
    setResults(null);
    
    try {
      // Use the public guest search endpoint
      const response = await axios.get(`${API}/guest-search`, {
        params: { query: query.trim() }
      });
      console.log("Search response:", response.data);
      setResults(response.data);
    } catch (error) {
      console.error("Search error:", error);
      toast.error("Error searching for products");
    } finally {
      setLoading(false);
    }
  };

  // Get the lowest price for a product
  const getLowestPrice = (productId) => {
    if (!results || !results.prices || !results.prices[productId]) return null;
    
    const prices = results.prices[productId];
    if (prices.length === 0) return null;
    
    return prices.reduce((min, price) => 
      price.price < min.price ? price : min, prices[0]);
  };

  // Function to prepare chart data for a product
  const prepareChartData = (productId) => {
    if (!results || !results.prices || !results.prices[productId]) {
      return null;
    }
    
    const prices = results.prices[productId];
    
    // Sort prices from lowest to highest
    const sortedPrices = [...prices].sort((a, b) => a.price - b.price);
    
    return {
      labels: sortedPrices.map(price => price.store),
      datasets: [
        {
          label: 'Price (£)',
          data: sortedPrices.map(price => price.price),
          backgroundColor: sortedPrices.map((_, index) => 
            index === 0 ? 'rgba(34, 197, 94, 0.7)' : 'rgba(99, 102, 241, 0.5)'
          ),
          borderColor: sortedPrices.map((_, index) => 
            index === 0 ? 'rgb(34, 197, 94)' : 'rgb(79, 70, 229)'
          ),
          borderWidth: 1,
        }
      ]
    };
  };

  return (
    <div className="min-h-screen bg-gray-100">
      <div className="container mx-auto px-4 py-8">
        <div className="bg-white rounded-lg shadow-lg p-6 mb-8">
          <div className="text-center mb-8">
            <h1 className="text-3xl font-bold mb-4">UK Grocery Price Comparison</h1>
            <p className="text-xl text-gray-600">Find the best deals across top UK supermarkets</p>
          </div>
          
          <div className="max-w-3xl mx-auto">
            <h2 className="text-2xl font-bold mb-6">Search Products</h2>
            <form onSubmit={handleSearch} className="mb-6">
              <div className="flex">
                <input
                  type="text"
                  className="flex-grow px-4 py-2 border border-gray-300 rounded-l-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  placeholder="Enter product name (e.g., milk, bread, apples)"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  required
                />
                <button
                  type="submit"
                  className="bg-indigo-600 hover:bg-indigo-700 text-white px-6 py-2 rounded-r-md"
                  disabled={loading}
                >
                  {loading ? "Searching..." : "Search"}
                </button>
              </div>
            </form>
          </div>
          
          {loading && (
            <div className="text-center py-8">
              <div className="inline-block animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-indigo-600"></div>
              <p className="mt-2 text-gray-600">Searching across UK supermarkets...</p>
            </div>
          )}
          
          {results && results.products && results.products.length > 0 && (
            <div>
              <h3 className="text-xl font-semibold mb-4">Results for "{query}"</h3>
              <div className="grid md:grid-cols-2 gap-6">
                {results.products.map(product => {
                  const lowestPrice = getLowestPrice(product.id);
                  const chartData = prepareChartData(product.id);
                  
                  return (
                    <div key={product.id} className="bg-gray-50 rounded-lg shadow border border-gray-200 overflow-hidden">
                      <div className="p-4 border-b border-gray-200">
                        <div className="flex items-start">
                          {product.image_url && (
                            <div className="flex-shrink-0 mr-4">
                              <img 
                                src={product.image_url} 
                                alt={product.name}
                                className="w-24 h-24 object-cover rounded-md"
                                onError={(e) => {
                                  e.target.onerror = null;
                                  e.target.src = "https://via.placeholder.com/100x100?text=No+Image";
                                }}
                              />
                            </div>
                          )}
                          <div className="flex-grow">
                            <h4 className="text-lg font-semibold mb-2">{product.name}</h4>
                            <p className="text-sm text-gray-600 mb-1">Category: {product.category}</p>
                            
                            {/* Display weight, quantity, and unit information */}
                            <div className="mb-2">
                              {product.weight && (
                                <span className="inline-block bg-gray-200 rounded-full px-2 py-1 text-xs font-semibold text-gray-700 mr-2 mb-1">
                                  {product.weight}
                                </span>
                              )}
                              {product.quantity && (
                                <span className="inline-block bg-gray-200 rounded-full px-2 py-1 text-xs font-semibold text-gray-700 mr-2 mb-1">
                                  Qty: {product.quantity}
                                </span>
                              )}
                              {product.unit && (
                                <span className="inline-block bg-gray-200 rounded-full px-2 py-1 text-xs font-semibold text-gray-700 mr-2 mb-1">
                                  {product.unit}
                                </span>
                              )}
                            </div>
                            
                            {lowestPrice && (
                              <div className="flex items-center">
                                <span className="font-bold text-green-600 mr-2">Best Price: £{lowestPrice.price.toFixed(2)}</span>
                                <span className="text-sm text-gray-600">at {lowestPrice.store}</span>
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                      
                      {chartData && (
                        <div className="p-4">
                          <h5 className="text-sm font-semibold mb-2">Price Comparison</h5>
                          <div className="h-64">
                            <Bar 
                              data={chartData} 
                              options={{
                                responsive: true,
                                maintainAspectRatio: false,
                                plugins: {
                                  legend: {
                                    display: false,
                                  },
                                  tooltip: {
                                    callbacks: {
                                      label: function(context) {
                                        return `£${context.parsed.y.toFixed(2)}`;
                                      }
                                    }
                                  }
                                },
                                scales: {
                                  y: {
                                    beginAtZero: true,
                                    ticks: {
                                      callback: function(value) {
                                        return '£' + value.toFixed(2);
                                      }
                                    }
                                  }
                                }
                              }}
                            />
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
              
              <div className="mt-8 text-center">
                <p className="text-gray-600 mb-4">Create an account to save products and shopping lists</p>
                <div className="flex justify-center space-x-4">
                  <Link to="/register" className="bg-green-600 hover:bg-green-700 text-white px-6 py-2 rounded-md">
                    Register
                  </Link>
                  <Link to="/login" className="bg-indigo-600 hover:bg-indigo-700 text-white px-6 py-2 rounded-md">
                    Login
                  </Link>
                </div>
              </div>
            </div>
          )}
          
          {results && results.products && results.products.length === 0 && (
            <div className="text-center py-8">
              <p className="text-gray-600">No products found for "{query}". Try a different search term.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// Login component
function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const auth = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    
    const result = await auth.login(email, password);
    
    setLoading(false);
    
    if (result.success) {
      toast.success("Login successful");
      navigate("/");
    } else {
      toast.error(result.message);
    }
  };

  if (auth.user) {
    return <Navigate to="/" />;
  }

  return (
    <div className="min-h-screen bg-gray-100 flex items-center justify-center">
      <div className="max-w-md w-full bg-white rounded-lg shadow-md overflow-hidden">
        <div className="bg-indigo-600 py-4 px-6">
          <h2 className="text-2xl font-bold text-white text-center">Login</h2>
        </div>
        <form onSubmit={handleSubmit} className="py-6 px-8">
          <div className="mb-4">
            <label className="block text-gray-700 text-sm font-bold mb-2" htmlFor="email">
              Email
            </label>
            <input
              className="appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline"
              id="email"
              type="email"
              placeholder="Email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div className="mb-6">
            <label className="block text-gray-700 text-sm font-bold mb-2" htmlFor="password">
              Password
            </label>
            <input
              className="appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline"
              id="password"
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          <div className="flex items-center justify-between">
            <button
              className="bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline w-full"
              type="submit"
              disabled={loading}
            >
              {loading ? "Logging in..." : "Login"}
            </button>
          </div>
          <div className="text-center mt-4">
            <p className="text-gray-600 text-sm">
              Don't have an account?{" "}
              <Link to="/register" className="text-indigo-600 hover:text-indigo-800">
                Register
              </Link>
            </p>
          </div>
        </form>
      </div>
    </div>
  );
}

// Register component
function Register() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const auth = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (password !== confirmPassword) {
      toast.error("Passwords do not match");
      return;
    }
    
    setLoading(true);
    const result = await auth.register(name, email, password);
    setLoading(false);
    
    if (result.success) {
      toast.success("Registration successful. Please login.");
      navigate("/login");
    } else {
      toast.error(result.message);
    }
  };

  if (auth.user) {
    return <Navigate to="/" />;
  }

  return (
    <div className="min-h-screen bg-gray-100 flex items-center justify-center">
      <div className="max-w-md w-full bg-white rounded-lg shadow-md overflow-hidden">
        <div className="bg-green-600 py-4 px-6">
          <h2 className="text-2xl font-bold text-white text-center">Register</h2>
        </div>
        <form onSubmit={handleSubmit} className="py-6 px-8">
          <div className="mb-4">
            <label className="block text-gray-700 text-sm font-bold mb-2" htmlFor="name">
              Name
            </label>
            <input
              className="appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline"
              id="name"
              type="text"
              placeholder="Full Name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </div>
          <div className="mb-4">
            <label className="block text-gray-700 text-sm font-bold mb-2" htmlFor="email">
              Email
            </label>
            <input
              className="appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline"
              id="email"
              type="email"
              placeholder="Email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div className="mb-4">
            <label className="block text-gray-700 text-sm font-bold mb-2" htmlFor="password">
              Password
            </label>
            <input
              className="appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline"
              id="password"
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          <div className="mb-6">
            <label className="block text-gray-700 text-sm font-bold mb-2" htmlFor="confirmPassword">
              Confirm Password
            </label>
            <input
              className="appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline"
              id="confirmPassword"
              type="password"
              placeholder="Confirm Password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
            />
          </div>
          <div className="flex items-center justify-between">
            <button
              className="bg-green-600 hover:bg-green-700 text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline w-full"
              type="submit"
              disabled={loading}
            >
              {loading ? "Registering..." : "Register"}
            </button>
          </div>
          <div className="text-center mt-4">
            <p className="text-gray-600 text-sm">
              Already have an account?{" "}
              <Link to="/login" className="text-green-600 hover:text-green-800">
                Login
              </Link>
            </p>
          </div>
        </form>
      </div>
    </div>
  );
}

// Search component
function Search() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const { user } = useAuth();

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;
    
    setLoading(true);
    // Clear previous results first
    setResults(null);
    
    try {
      const token = localStorage.getItem("token");
      const response = await axios.get(`${API}/search`, {
        params: { query: query.trim() },
        headers: { Authorization: `Bearer ${token}` },
      });
      console.log("Search response:", response.data);
      setResults(response.data);
    } catch (error) {
      console.error("Search error:", error);
      toast.error("Error searching for products");
    } finally {
      setLoading(false);
    }
  };

  // Get the lowest price for a product
  const getLowestPrice = (productId) => {
    if (!results || !results.prices || !results.prices[productId]) return null;
    
    const prices = results.prices[productId];
    if (prices.length === 0) return null;
    
    return prices.reduce((min, price) => 
      price.price < min.price ? price : min, prices[0]);
  };

  // Function to prepare chart data for a product
  const prepareChartData = (productId) => {
    if (!results || !results.prices || !results.prices[productId]) {
      return null;
    }
    
    const prices = results.prices[productId];
    
    // Sort prices from lowest to highest
    const sortedPrices = [...prices].sort((a, b) => a.price - b.price);
    
    return {
      labels: sortedPrices.map(price => price.store),
      datasets: [
        {
          label: 'Price (£)',
          data: sortedPrices.map(price => price.price),
          backgroundColor: sortedPrices.map((_, index) => 
            index === 0 ? 'rgba(34, 197, 94, 0.7)' : 'rgba(99, 102, 241, 0.5)'
          ),
          borderColor: sortedPrices.map((_, index) => 
            index === 0 ? 'rgb(34, 197, 94)' : 'rgb(79, 70, 229)'
          ),
          borderWidth: 1,
        }
      ]
    };
  };

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="bg-white rounded-lg shadow-lg p-6 mb-8">
        <h2 className="text-2xl font-bold mb-6">Search Products</h2>
        <form onSubmit={handleSearch} className="mb-6">
          <div className="flex">
            <input
              type="text"
              className="flex-grow px-4 py-2 border border-gray-300 rounded-l-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
              placeholder="Enter product name (e.g., milk, bread, apples)"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              required
            />
            <button
              type="submit"
              className="bg-indigo-600 hover:bg-indigo-700 text-white px-6 py-2 rounded-r-md"
              disabled={loading}
            >
              {loading ? "Searching..." : "Search"}
            </button>
          </div>
        </form>
        
        {loading && (
          <div className="text-center py-8">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-indigo-600"></div>
            <p className="mt-2 text-gray-600">Searching across UK supermarkets...</p>
          </div>
        )}
        
        {results && results.products && results.products.length > 0 && (
          <div>
            <h3 className="text-xl font-semibold mb-4">Results for "{query}"</h3>
            <div className="grid md:grid-cols-2 gap-6">
              {results.products.map(product => {
                const lowestPrice = getLowestPrice(product.id);
                const chartData = prepareChartData(product.id);
                
                return (
                  <div key={product.id} className="bg-gray-50 rounded-lg shadow border border-gray-200 overflow-hidden">
                    <div className="p-4 border-b border-gray-200">
                      <div className="flex items-start">
                        {product.image_url && (
                          <div className="flex-shrink-0 mr-4">
                            <img 
                              src={product.image_url} 
                              alt={product.name}
                              className="w-24 h-24 object-cover rounded-md"
                              onError={(e) => {
                                e.target.onerror = null;
                                e.target.src = "https://via.placeholder.com/100x100?text=No+Image";
                              }}
                            />
                          </div>
                        )}
                        <div className="flex-grow">
                          <h4 className="text-lg font-semibold mb-2">{product.name}</h4>
                          <p className="text-sm text-gray-600 mb-1">Category: {product.category}</p>
                          
                          {/* Display weight, quantity, and unit information */}
                          <div className="mb-2">
                            {product.weight && (
                              <span className="inline-block bg-gray-200 rounded-full px-2 py-1 text-xs font-semibold text-gray-700 mr-2 mb-1">
                                {product.weight}
                              </span>
                            )}
                            {product.quantity && (
                              <span className="inline-block bg-gray-200 rounded-full px-2 py-1 text-xs font-semibold text-gray-700 mr-2 mb-1">
                                Qty: {product.quantity}
                              </span>
                            )}
                            {product.unit && (
                              <span className="inline-block bg-gray-200 rounded-full px-2 py-1 text-xs font-semibold text-gray-700 mr-2 mb-1">
                                {product.unit}
                              </span>
                            )}
                          </div>
                          
                          {lowestPrice && (
                            <div className="flex items-center">
                              <span className="font-bold text-green-600 mr-2">Best Price: £{lowestPrice.price.toFixed(2)}</span>
                              <span className="text-sm text-gray-600">at {lowestPrice.store}</span>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                    
                    {chartData && (
                      <div className="p-4">
                        <h5 className="text-sm font-semibold mb-2">Price Comparison</h5>
                        <div className="h-64">
                          <Bar 
                            data={chartData} 
                            options={{
                              responsive: true,
                              maintainAspectRatio: false,
                              plugins: {
                                legend: {
                                  display: false,
                                },
                                tooltip: {
                                  callbacks: {
                                    label: function(context) {
                                      return `£${context.parsed.y.toFixed(2)}`;
                                    }
                                  }
                                }
                              },
                              scales: {
                                y: {
                                  beginAtZero: true,
                                  ticks: {
                                    callback: function(value) {
                                      return '£' + value.toFixed(2);
                                    }
                                  }
                                }
                              }
                            }}
                          />
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}
        
        {results && results.products && results.products.length === 0 && (
          <div className="text-center py-8">
            <p className="text-gray-600">No products found for "{query}". Try a different search term.</p>
          </div>
        )}
      </div>
    </div>
  );
}

// Shopping Lists component
function ShoppingLists() {
  const [lists, setLists] = useState([]);
  const [loading, setLoading] = useState(true);
  const [listName, setListName] = useState("");
  const [showCreateForm, setShowCreateForm] = useState(false);
  const { user } = useAuth();

  useEffect(() => {
    fetchLists();
  }, []);

  const fetchLists = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem("token");
      const response = await axios.get(`${API}/shopping-lists`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setLists(response.data);
    } catch (error) {
      console.error("Error fetching shopping lists:", error);
      toast.error("Error loading shopping lists");
    } finally {
      setLoading(false);
    }
  };

  const handleCreateList = async (e) => {
    e.preventDefault();
    if (!listName.trim()) return;
    
    try {
      const token = localStorage.getItem("token");
      await axios.post(
        `${API}/shopping-lists`,
        {
          name: listName,
          user_id: user.id,
          items: [],
        },
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      
      setListName("");
      setShowCreateForm(false);
      toast.success("Shopping list created");
      fetchLists();
    } catch (error) {
      console.error("Error creating shopping list:", error);
      toast.error("Error creating shopping list");
    }
  };

  const handleDeleteList = async (listId) => {
    if (!window.confirm("Are you sure you want to delete this shopping list?")) {
      return;
    }
    
    try {
      const token = localStorage.getItem("token");
      await axios.delete(`${API}/shopping-lists/${listId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      
      toast.success("Shopping list deleted");
      setLists(lists.filter(list => list.id !== listId));
    } catch (error) {
      console.error("Error deleting shopping list:", error);
      toast.error("Error deleting shopping list");
    }
  };

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="bg-white rounded-lg shadow-lg p-6 mb-8">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-2xl font-bold">Your Shopping Lists</h2>
          <button
            className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-md"
            onClick={() => setShowCreateForm(!showCreateForm)}
          >
            {showCreateForm ? "Cancel" : "Create New List"}
          </button>
        </div>
        
        {showCreateForm && (
          <div className="bg-gray-50 p-4 rounded-md mb-6">
            <form onSubmit={handleCreateList}>
              <div className="flex">
                <input
                  type="text"
                  className="flex-grow px-4 py-2 border border-gray-300 rounded-l-md focus:outline-none focus:ring-2 focus:ring-green-500"
                  placeholder="Shopping list name"
                  value={listName}
                  onChange={(e) => setListName(e.target.value)}
                  required
                />
                <button
                  type="submit"
                  className="bg-green-600 hover:bg-green-700 text-white px-6 py-2 rounded-r-md"
                >
                  Create
                </button>
              </div>
            </form>
          </div>
        )}
        
        {loading ? (
          <div className="text-center py-8">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-indigo-600"></div>
            <p className="mt-2 text-gray-600">Loading your shopping lists...</p>
          </div>
        ) : (
          <>
            {lists.length === 0 ? (
              <div className="text-center py-8 bg-gray-50 rounded-lg">
                <p className="text-gray-600 mb-4">You don't have any shopping lists yet.</p>
                <button
                  className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-md"
                  onClick={() => setShowCreateForm(true)}
                >
                  Create Your First List
                </button>
              </div>
            ) : (
              <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
                {lists.map(list => (
                  <div key={list.id} className="bg-gray-50 rounded-lg shadow border border-gray-200 overflow-hidden">
                    <div className="p-4 border-b border-gray-200 flex justify-between items-center">
                      <h3 className="text-lg font-semibold">{list.name}</h3>
                      <div className="flex space-x-2">
                        <Link
                          to={`/shopping-lists/${list.id}`}
                          className="bg-indigo-600 hover:bg-indigo-700 text-white px-3 py-1 rounded-md text-sm"
                        >
                          View
                        </Link>
                        <button
                          onClick={() => handleDeleteList(list.id)}
                          className="bg-red-600 hover:bg-red-700 text-white px-3 py-1 rounded-md text-sm"
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                    <div className="p-4">
                      <p className="text-sm text-gray-600 mb-2">
                        Created: {new Date(list.created_at).toLocaleDateString()}
                      </p>
                      <p className="text-sm text-gray-600">
                        {list.items.length} item{list.items.length !== 1 ? 's' : ''}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

// Stores component
function Stores() {
  const [stores, setStores] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchStores = async () => {
      try {
        const response = await axios.get(`${API}/stores`);
        setStores(response.data);
      } catch (error) {
        console.error("Error fetching stores:", error);
        toast.error("Error loading store information");
      } finally {
        setLoading(false);
      }
    };

    fetchStores();
  }, []);

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="bg-white rounded-lg shadow-lg p-6">
        <h2 className="text-2xl font-bold mb-6">UK Grocery Stores</h2>
        
        {loading ? (
          <div className="text-center py-8">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-indigo-600"></div>
            <p className="mt-2 text-gray-600">Loading store information...</p>
          </div>
        ) : (
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {stores.map((store, index) => (
              <div key={index} className="bg-gray-50 rounded-lg shadow border border-gray-200 overflow-hidden">
                <div className="p-4">
                  <h3 className="text-lg font-semibold mb-2">{store.name}</h3>
                  <a
                    href={store.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-indigo-600 hover:text-indigo-800 text-sm"
                  >
                    Visit Website
                  </a>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// Router component that has access to auth context
function AppRouter() {
  const auth = useAuth();
  
  return (
    <>
      <Navigation />
      <ToastContainer position="top-right" autoClose={3000} />
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/guest-search" element={<GuestSearch />} />
        <Route
          path="/"
          element={
            auth.user ? (
              <Home />
            ) : (
              <Navigate to="/guest-search" />
            )
          }
        />
        <Route
          path="/search"
          element={
            <ProtectedRoute>
              <Search />
            </ProtectedRoute>
          }
        />
        <Route
          path="/shopping-lists"
          element={
            <ProtectedRoute>
              <ShoppingLists />
            </ProtectedRoute>
          }
        />
        <Route
          path="/stores"
          element={
            <Stores />
          }
        />
        <Route path="*" element={<Navigate to={auth.user ? "/" : "/guest-search"} />} />
      </Routes>
    </>
  );
}

// Main App component
function App() {
  return (
    <div className="App bg-gray-100 min-h-screen">
      <AuthProvider>
        <BrowserRouter>
          <AppRouter />
        </BrowserRouter>
      </AuthProvider>
    </div>
  );
}

export default App;
